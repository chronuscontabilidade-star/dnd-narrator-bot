import asyncio
import json
import logging
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from google import genai
except Exception:  # pragma: no cover - SDK optional in offline environments
    genai = None

log = logging.getLogger(__name__)

from .game.adventure import AdventureState, adventure_generation_prompt, empty_adventure_state

SYSTEM_PROMPT = """Você é um Mestre de RPG experiente e criativo especializado em D&D 5e.
Você narra aventuras imersivas em português do Brasil com descrições vívidas e tensão dramática.
Sempre mantenha consistência com o contexto da aventura e as ações anteriores.
Seja criativo, mas não invente fatos que contradigam o estado atual da sessão.
Retorne sempre JSON válido, sem markdown, sem explicações extras.
"""


class Narrator:
    def __init__(self, api_key: str):
        self.api_key = api_key or ""
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.alt_api_key = os.getenv("AI_API_KEY", "")
        self.alt_base_url = (os.getenv("AI_BASE_URL", "") or "").rstrip("/")
        self.alt_model = os.getenv("AI_MODEL", "")
        self.bastiao_base_url = (os.getenv("BASTIAO_BASE_URL", "") or "").rstrip("/")
        self.bastiao_api_key = os.getenv("BASTIAO_API_KEY", "")
        self.bastiao_model = os.getenv("BASTIAO_MODEL", "")
        self._provider_cooldowns = {}
        self._cooldown_seconds = int(os.getenv("AI_PROVIDER_COOLDOWN", "300"))
        self._request_timeout = float(os.getenv("AI_REQUEST_TIMEOUT", "20"))
        self.client = None
        self.model = None
        self.image_model = None
        self.provider_status = "offline"

        if self.api_key and genai is not None:
            self.client = genai.Client(api_key=self.api_key)
            self.model = self.client
            self.image_model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
            self.provider_status = f"gemini:{self.model_name}"
        elif self.api_key:
            self.provider_status = f"gemini-rest:{self.model_name}"
        else:
            log.warning("Gemini indisponível; usando narrador offline por padrão.")

        if self.alt_api_key and self.alt_base_url and self.alt_model:
            log.info("Provedor alternativo configurado: %s", self.alt_model)
        if self.bastiao_api_key and self.bastiao_base_url and self.bastiao_model:
            log.info("Bastião local configurado: %s", self.bastiao_model)

    def _cooldown_provider(self, provider: str, exc: Exception):
        self._provider_cooldowns[provider] = time.time() + self._cooldown_seconds
        log.warning("Provider %s entrou em cooldown por erro: %s", provider, exc)

    def _provider_available(self, provider: str) -> bool:
        until = self._provider_cooldowns.get(provider)
        if until and time.time() < until:
            return False
        return True

    def _parse_json(self, raw: str):
        if raw is None:
            raise ValueError("Resposta vazia da IA")
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
            text = re.sub(r"\s*```\s*$", "", text, flags=re.I)
        text = text.strip()
        if not text:
            raise ValueError("Resposta vazia depois do parse")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Heurística para extrair um JSON embutido de blocos de texto
            match = re.search(r"\{.*\}", text, flags=re.S)
            if match:
                return json.loads(match.group(0))
            raise

    def _offline_scene_seed(self, chat_id: int) -> dict:
        seed = (chat_id if chat_id else 1) % 4
        templates = [
            {
                "titulo": "As Cinzas do Farol Antigo",
                "narrativa": "Um farol abandonado treme ao longo da tempestade. Pegadas recentes cruzam o chão de pedra, e a porta de ferro da torre parece estar parcialmente aberta. O silêncio pesa mais que o vento.",
                "contexto": "Localização: Farol Antigo. Ameaça: ruínas despertas. Objetivo: investigar a torre e descobrir por que as pegadas voltaram a aparecer.",
            },
            {
                "titulo": "O Juramento da Floresta Sombria",
                "narrativa": "A floresta emudeceu quando a lua apareceu acima das copas. Entre as árvores, uma clareira se abre com um altar coberto por musgo e runas antigas, como se a natureza estivesse esperando alguém ser corajoso o bastante para despertar a promessa.",
                "contexto": "Localização: Floresta Sombria. Ameaça: matilha de criaturas e altar antigo. Objetivo: descobrir o que a clareira guarda e por que a magia está despertando.",
            },
            {
                "titulo": "A Cripta de Pedra Viva",
                "narrativa": "Uma câmara sepulcral respira por baixo da cidade. O ar cheira a poeira de túmulos e a magia antiga. Alguém já esteve ali antes, e o eco da descoberta parece levar o grupo em direção a um segredo enterrado.",
                "contexto": "Localização: Cripta de Pedra Viva. Ameaça: guardas mortos e portas seladas. Objetivo: explorar o interior e quebrar o selo que prende a memória da cidade.",
            },
            {
                "titulo": "O Templo do Vento Silencioso",
                "narrativa": "Pilares quebrados cercam um templo abandonado em meio ao deserto. Há música no vento, mas não é natural. Cada passo ecoa como um aviso: a lenda ainda não terminou, e algo dorme sob o altar central.",
                "contexto": "Localização: Templo do Vento Silencioso. Ameaça: ventos encantados e guardianas anciãs. Objetivo: entrar no templo e revelar a verdade sobre o sussurro do vento.",
            },
        ]
        return templates[seed]

    def _offline_personagem(self, nome: str, classe: str, raca: str, detalhes: str = "") -> dict:
        racas_bonus = {
            "Humano": {"Força": 1, "Destreza": 1, "Constituição": 1, "Inteligência": 1, "Sabedoria": 1, "Carisma": 1},
            "Elfo": {"Destreza": 2, "Inteligência": 1},
            "Anão": {"Constituição": 2, "Sabedoria": 1},
            "Halfling": {"Destreza": 2, "Carisma": 1},
            "Tiefling": {"Inteligência": 1, "Carisma": 2},
            "Meio-Orc": {"Força": 2, "Constituição": 1},
        }
        base = {"Força": 12, "Destreza": 12, "Constituição": 12, "Inteligência": 12, "Sabedoria": 12, "Carisma": 12}
        for attr, bonus in racas_bonus.get(raca, {}).items():
            base[attr] = base.get(attr, 10) + bonus
        if classe == "Guerreiro":
            base["Força"] += 2
            base["Constituição"] += 1
        elif classe == "Bárbaro":
            base["Força"] += 3
            base["Constituição"] += 1
        elif classe == "Ladino":
            base["Destreza"] += 2
            base["Inteligência"] += 1
        elif classe == "Mago":
            base["Inteligência"] += 3
            base["Destreza"] += 1
        elif classe == "Clérigo":
            base["Sabedoria"] += 2
            base["Constituição"] += 1
        elif classe == "Ranger":
            base["Destreza"] += 2
            base["Sabedoria"] += 1

        hist = f"{nome} é um {classe.lower()} de {raca.lower()} que nasceu para seguir em direção ao desconhecido."
        if detalhes and detalhes.strip().lower() not in {"nenhum", "nenhuma", "n/a", "nao", "não"}:
            hist = hist + f" Seus detalhes pessoais incluem: {detalhes.strip()}"
        hist += " No momento, o personagem busca um propósito claro e enfrenta o mundo com coragem, disciplina e curiosidade."
        return {"atributos": base, "historia": hist}

    def _offline_sugestoes(self, sessao: dict, personagem: dict) -> list:
        contexto = (sessao or {}).get("contexto", "")
        base = [
            "Investigar o ponto mais ameaçador da cena",
            "Conversar com o NPC mais suspeito",
            "Procurar uma rota ou passagem secreta",
        ]
        if "balcão" in contexto.lower():
            base.insert(0, "Examinar atentamente o balcão em busca de pistas")
        if "inimigos" in contexto.lower() or "ameaça" in contexto.lower():
            base.insert(0, "Avaliar a melhor forma de enfrentar os inimigos")
        if "porta" in contexto.lower() or "passagem" in contexto.lower():
            base.insert(0, "Explorar a passagem ou porta escondida")
        return [{"acao": item, "atributo": "Destreza", "cd": 12, "risco": "médio"} for item in base[:3]]

    def _call_gemini_json(self, prompt: str):
        if not self.api_key or genai is None or not self.client:
            raise RuntimeError("Gemini não configurado")
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "response_mime_type": "application/json",
            },
        )
        text = response.text if hasattr(response, "text") else str(response)
        return self._parse_json(text)

    def _call_openai_compatible_json(self, base_url: str, api_key: str, model: str, prompt: str, provider: str):
        if not base_url or not model:
            raise RuntimeError(f"{provider} não configurado")
        url = base_url if base_url.endswith("/chat/completions") else f"{base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.8,
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{provider} HTTP {exc.code}: {exc.reason}") from exc
        except Exception as exc:  # pragma: no cover - network path
            raise RuntimeError(f"Falha de rede em {provider}: {exc}") from exc
        data = json.loads(body)
        try:
            return self._parse_json(data["choices"][0]["message"]["content"])
        except Exception:
            # algumas APIs retornam uma string simples em content
            content = data.get("choices", [{}])[0].get("message", {}).get("content")
            if isinstance(content, str):
                return self._parse_json(content)
            raise

    async def _request_json(self, prompt: str):
        providers = []
        if self.api_key and genai is not None and self.model and self._provider_available("gemini"):
            providers.append(("gemini", lambda: self._call_gemini_json(prompt)))
        if self.alt_base_url and self.alt_model and self._provider_available("alternative"):
            providers.append(("alternative", lambda: self._call_openai_compatible_json(self.alt_base_url, self.alt_api_key, self.alt_model, prompt, "alternative")))
        if self.bastiao_base_url and self.bastiao_model and self._provider_available("bastiao"):
            providers.append(("bastiao", lambda: self._call_openai_compatible_json(self.bastiao_base_url, self.bastiao_api_key, self.bastiao_model, prompt, "bastiao")))

        if not providers:
            raise RuntimeError("Nenhum provedor ativo disponível")

        last_error = None
        for name, worker in providers:
            try:
                return await asyncio.to_thread(worker)
            except Exception as exc:
                last_error = exc
                self._cooldown_provider(name, exc)
                log.warning("Falha no provider %s: %s", name, exc)
        raise last_error or RuntimeError("Falha ao obter resposta da IA")

    async def iniciar_aventura(self, chat_id: int) -> dict:
        """Gera uma campanha nova seguindo o contrato AdventureState.

        A aventura não é pré-gravada: cada chamada pede uma nova geração à IA.
        O estado retornado serve apenas como snapshot persistente da campanha
        atualmente em jogo.
        """
        seed = self._offline_scene_seed(chat_id)
        prompt = adventure_generation_prompt()
        try:
            data = await self._request_json(prompt)
            state = AdventureState.from_dict(data)
            payload = state.to_dict()
            narrativa = payload["narrativa_inicial"]
            progresso = payload["progresso"]
            local_id = progresso["local_atual"]
            local = next(
                (item for item in payload["locais"] if item.get("id") == local_id),
                None,
            )
            local_nome = local.get("nome", "local desconhecido") if local else "local desconhecido"
            payload["narrativa"] = narrativa
            payload["contexto"] = (
                f"Aventura: {payload['aventura']['titulo']}. "
                f"Local atual: {local_nome}. "
                f"Objetivo(s): {', '.join(q.get('titulo', '') for q in payload['quests'] if q.get('status') == 'ativa') or 'explorar a situação'}."
            )
            return payload
        except Exception as exc:
            log.warning("IA indisponível para gerar aventura nova; usando gerador mínimo local: %s", exc)

        fallback = empty_adventure_state(
            titulo=seed["titulo"],
            resumo=seed["contexto"],
            local_inicial=seed["titulo"],
            narrativa_inicial=seed["narrativa"],
        )
        fallback["narrativa"] = seed["narrativa"]
        fallback["contexto"] = seed["contexto"]
        return fallback

    @staticmethod
    def _validar_avaliacao(data: dict) -> dict:
        if not isinstance(data, dict):
            raise ValueError("Avaliação da IA não é um objeto JSON")
        precisa = data.get("precisa_teste")
        if not isinstance(precisa, bool):
            raise ValueError("precisa_teste inválido")
        atributo = data.get("atributo", "Destreza")
        atributos_validos = {"Força", "Destreza", "Constituição", "Inteligência", "Sabedoria", "Carisma"}
        if atributo not in atributos_validos:
            atributo = "Destreza"
        try:
            cd = int(data.get("cd", 12))
        except (TypeError, ValueError):
            cd = 12
        cd = max(1, min(cd, 30))
        return {**data, "precisa_teste": precisa, "atributo": atributo, "cd": cd}

    @staticmethod
    def _validar_ficha(data: dict) -> dict:
        if not isinstance(data, dict) or not isinstance(data.get("atributos"), dict) or not data.get("historia"):
            raise ValueError("Ficha inválida")
        nomes = {"Força", "Destreza", "Constituição", "Inteligência", "Sabedoria", "Carisma"}
        atributos = {}
        for nome in nomes:
            try:
                valor = int(data["atributos"].get(nome, 10))
            except (TypeError, ValueError):
                valor = 10
            atributos[nome] = max(1, min(valor, 30))
        return {"atributos": atributos, "historia": str(data["historia"])[:4000]}

    async def criar_personagem(self, nome: str, classe: str, raca: str, detalhes: str = "") -> dict:
        prompt = (
            "Crie uma ficha de personagem de D&D 5e em JSON com chaves 'atributos' e 'historia'. "
            "Use valores entre 8 e 18. Mantenha fidelidade à raça, classe e ao conceito fornecido. "
            "A história deve parecer escrita especificamente para esse personagem: conecte raça, classe, "
            "profissão, arquétipo, manias, medos, objetivos e demais detalhes fornecidos. "
            "Não contradiga os detalhes do jogador e não invente uma raça ou classe diferente. "
            f"Nome: {nome}. Raça: {raca}. Classe: {classe}. Conceito e detalhes do jogador: {detalhes or 'nenhum'}."
        )
        try:
            data = await self._request_json(prompt)
            if isinstance(data, dict):
                return self._validar_ficha(data)
        except Exception as exc:
            log.warning("IA indisponível para criar personagem; usando fallback offline: %s", exc)
        return self._offline_personagem(nome, classe, raca, detalhes)

    @staticmethod
    def _normalizar_acao(texto: str) -> str:
        import unicodedata
        valor = (texto or "").lower()
        return "".join(
            ch for ch in unicodedata.normalize("NFD", valor)
            if unicodedata.category(ch) != "Mn"
        )

    @classmethod
    def _classificar_acao_obvia(cls, acao: str):
        """Retorna False para ações narrativas simples, True para ações que exigem teste,
        ou None quando a ação é ambígua e a IA pode decidir.
        """
        texto = cls._normalizar_acao(acao)

        # Ações rotineiras: não gastam teste só para movimentar a narrativa.
        simples = (
            "andar", "caminhar", "caminho", "ir ate", "vou ate", "aproximar",
            "aproximar-se", "entrar", "sair", "seguir", "olhar", "observar",
            "ver", "falar", "dizer", "perguntar", "responder", "sentar",
            "levantar", "esperar", "continuar", "parar", "voltar",
        )
        if any(item in texto for item in simples):
            return False

        # Ações explicitamente arriscadas ou dependentes de perícia.
        arriscadas = (
            "bater", "atacar", "golpear", "lutar", "roubar", "furtar",
            "inspecionar", "inspeciono", "analisar", "analisar", "investigar",
            "procurar", "buscar pistas", "tentar ouvir", "ouvir atentamente",
            "escutar", "perceber", "rastrear", "seguir pegadas", "esconder",
            "esconder-se", "furtividade", "arrombar", "abrir fechadura",
            "desarmar", "enganar", "persuadir", "intimidar", "convencer",
            "blefar", "escalar", "nadar", "saltar", "desarmar armadilha",
        )
        if any(item in texto for item in arriscadas):
            return True

        return None

    async def avaliar_acao(self, sessao: dict, acao: str) -> dict:
        classificacao = self._classificar_acao_obvia(acao)
        from dice import detectar_atributo as _det
        atributo_detectado = _det(acao) or "Destreza"

        if classificacao is False:
            return {
                "precisa_teste": False,
                "atributo": atributo_detectado,
                "cd": 10,
                "motivo": "Ação narrativa simples; nenhum teste é necessário.",
            }

        if classificacao is True:
            return {
                "precisa_teste": True,
                "atributo": atributo_detectado,
                "cd": 12,
                "motivo": "Ação envolve risco, perícia ou habilidade.",
            }

        prompt = (
            "Avalie esta ação segundo D&D 5e. Só peça teste quando houver uma consequência "
            "relevante e o resultado for incerto. Ações rotineiras como andar, entrar, olhar, "
            "observar, falar, perguntar ou seguir por um caminho livre NÃO exigem rolagem. "
            "Ações como atacar, roubar, investigar, procurar pistas, analisar algo difícil, "
            "tentar ouvir algo oculto, persuadir, intimidar, furtividade ou superar um obstáculo "
            "podem exigir teste. Nunca peça rolagem apenas para preencher a narrativa. "
            "Retorne JSON: {'precisa_teste': true/false, 'atributo': 'Força', 'cd': 12, 'motivo': '...'} "
            f"Contexto: {sessao.get('contexto', '')}. Ação: {acao}"
        )
        try:
            data = await self._request_json(prompt)
            if isinstance(data, dict) and "precisa_teste" in data:
                return self._validar_avaliacao(data)
        except Exception as exc:
            log.warning("IA indisponível ao avaliar ação; usando regra local: %s", exc)

        return {
            "precisa_teste": False,
            "atributo": atributo_detectado,
            "cd": 10,
            "motivo": "IA indisponível e ação ambígua; seguindo sem bloquear o jogador.",
        }

    async def narrar_acao_com_dado(self, sessao: dict, personagem: dict, jogadores: list, acao: str, teste: dict | None, historico: list | None = None) -> dict:
        prompt = (
            "Narre a ação de um personagem em D&D em português do Brasil. "
            "Retorne JSON com chaves 'narrativa', 'novo_contexto' e 'sugestoes'. "
            f"Contexto atual: {sessao.get('contexto', '')}. "
            f"Estado estruturado da aventura: {json.dumps(sessao.get('aventura') or {}, ensure_ascii=False)}. "
            f"Personagem ativo: {personagem.get('nome')} "
            f"({personagem.get('classe')}, {personagem.get('raca')}). Ação: {acao}. "
            f"Teste: {teste}. Jogadores presentes: {[p.get('nome') for p in (jogadores or [])]}. "
            f"Histórico recente: {(historico or [])[-10:]}. "
        )
        try:
            data = await self._request_json(prompt)
            if isinstance(data, dict) and data.get("narrativa"):
                novo_contexto = data.get("novo_contexto") or sessao.get("contexto", "")
                sugestoes = data.get("sugestoes") or []
                return {"narrativa": data["narrativa"], "novo_contexto": novo_contexto, "sugestoes": sugestoes}
        except Exception as exc:
            log.warning("IA indisponível para narrar ação; usando fallback offline: %s", exc)

        contexto = sessao.get("contexto", "")
        nome = personagem.get("nome", "O personagem")
        texto = (acao or "").strip()
        normalizado = self._normalizar_acao(texto)

        # Fallback offline deve continuar a aventura, não repetir uma frase genérica.
        if "entrar" in normalizado and ("cripta" in normalizado or "caverna" in normalizado or "torre" in normalizado):
            narr = f"{nome} entra cuidadosamente no local. O ar muda assim que atravessa a passagem, e a entrada fica para trás enquanto os sons do lado de fora começam a desaparecer."
            evento = f"{nome} entrou no local."
        elif any(palavra in normalizado for palavra in ("procurar", "buscar", "investigar", "inspecionar", "analisar")):
            narr = f"{nome} examina o ambiente em busca de algo fora do lugar. Entre marcas, objetos e detalhes aparentemente comuns, há sinais que podem revelar uma pista."
            evento = f"{nome} procurou pistas no ambiente."
        elif any(palavra in normalizado for palavra in ("olhar", "observar", "ver")):
            narr = f"{nome} observa atentamente os arredores. A posição das entradas, os sons e os movimentos ao redor ficam mais claros."
            evento = f"{nome} observou os arredores."
        elif any(palavra in normalizado for palavra in ("falar", "perguntar", "dizer", "conversar")):
            narr = f"{nome} inicia uma conversa e coloca sua intenção às claras. A reação de quem está por perto passa a fazer parte da cena."
            evento = f"{nome} iniciou uma conversa."
        else:
            narr = f"{nome} realiza a ação: {texto}. A cena avança a partir dessa decisão."
            evento = f"{nome} realizou a ação: {texto}."

        resultado_txt = "teste bem-sucedido" if teste and teste.get("sucesso") else "teste falho" if teste else "sem teste"
        novo_contexto = (
            f"{contexto}\n"
            f"Evento: {evento} Resultado: {resultado_txt}"
        ).strip()

        sugestoes = [
            "Continuar explorando o local",
            "Observar detalhes importantes da cena",
            "Interagir com alguém ou alguma coisa presente",
        ]
        return {"narrativa": narr, "novo_contexto": novo_contexto, "sugestoes": sugestoes}

    async def sugerir_acoes(self, sessao: dict, personagem: dict) -> dict:
        prompt = (
            "Sugira 3 ações úteis para um personagem em D&D. Retorne JSON {'sugestoes': [{...}]}. "
            f"Contexto: {sessao.get('contexto', '')}. Personagem: {personagem.get('nome')}."
        )
        try:
            data = await self._request_json(prompt)
            if isinstance(data, dict) and isinstance(data.get("sugestoes"), list):
                return data
        except Exception as exc:
            log.warning("IA indisponível para sugerir ações; usando fallback offline: %s", exc)
        return {"sugestoes": self._offline_sugestoes(sessao, personagem)}

    async def gerar_cena(self, sessao: dict) -> dict:
        """Gera APENAS a descrição textual da cena. Imagem: use gerar_imagem()."""
        prompt = (
            "Descreva a cena visual atual da aventura em 2-3 frases cinematográficas em português do Brasil. "
            "Retorne JSON: {'descricao': 'descrição vívida da cena'}. "
            f"Contexto: {sessao.get('contexto', '')}"
        )
        try:
            data = await self._request_json(prompt)
            if isinstance(data, dict) and data.get("descricao"):
                return {"descricao": data["descricao"], "imagem_bytes": None}
        except Exception as exc:
            log.warning("IA indisponível para gerar cena; usando fallback offline: %s", exc)
        ctx = sessao.get("contexto", "")
        desc = f"A aventura continua. {ctx[:200]}" if ctx else "A cena se desenrola em silêncio tenso."
        return {"descricao": desc, "imagem_bytes": None}

    async def gerar_imagem(self, sessao: dict):
        if not self.api_key or not self.client or not self.image_model:
            return {"imagem_bytes": None, "descricao": "Sem imagem disponível."}
        try:
            prompt = (
                "Crie uma cena épica de fantasia para uma campanha de D&D. "
                f"Situação atual: {sessao.get('contexto', '')}"
            )
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.image_model,
                contents=prompt,
                config={"response_modalities": ["IMAGE"]},
            )
            for part in getattr(response, "parts", []) or []:
                inline = getattr(part, "inline_data", None)
                if inline is not None and getattr(inline, "data", None):
                    return {"imagem_bytes": inline.data, "descricao": "Cena gerada"}
        except Exception as exc:
            log.warning("Imagem falhou; usando fallback textual: %s", exc)
        return {"imagem_bytes": None, "descricao": "Cena textual disponível."}

    def _choose_provider(self):
        providers = [
            ("gemini", self.api_key and genai is not None and self.client is not None),
            ("alternative", bool(self.alt_base_url and self.alt_model)),
            ("bastiao", bool(self.bastiao_base_url and self.bastiao_model)),
        ]
        for name, enabled in providers:
            if enabled and self._provider_available(name):
                return name
        return "offline"


__all__ = ["Narrator", "SYSTEM_PROMPT"]
