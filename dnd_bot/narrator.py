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

try:
    from .game.adventure import AdventureState, adventure_generation_prompt, empty_adventure_state
except ImportError:  # suporte ao modo script: python dnd_bot/bot.py
    from game.adventure import AdventureState, adventure_generation_prompt, empty_adventure_state

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
        # O fallback não pode depender do chat_id. Isso fazia a mesma campanha
        # reaparecer sempre que a IA estivesse indisponível.
        return random.SystemRandom().choice(templates)

    def _offline_personagem(self, nome: str, classe: str, raca: str, detalhes: str = "") -> dict:
        try:
            from .game.character_creation import gerar_atributos
        except ImportError:
            from game.character_creation import gerar_atributos

        atributos = gerar_atributos(classe, raca)
        conceito = (detalhes or "").strip()
        sem_conceito = conceito.lower() in {"", "nenhum", "nenhuma", "n/a", "nao", "não"}
        if sem_conceito:
            hist = (
                f"{nome} cresceu entre os seus como um {classe.lower()} de origem {raca.lower()}, "
                "aprendendo cedo que sobreviver exige tanto coragem quanto escolhas difíceis. "
                "Agora carrega perguntas que ainda não conseguiu responder e procura uma razão para "
                "colocar suas habilidades a serviço de algo maior."
            )
        else:
            hist = (
                f"{nome} é um {classe.lower()} de origem {raca.lower()}, conhecido por viver segundo o seguinte "
                f"arquétipo: {conceito}. Esse traço não é apenas uma característica: ele moldou suas escolhas, "
                "sua maneira de enxergar outras pessoas e a forma como reage quando encontra perigo. "
                f"Quando a aventura começa, {nome} já traz consigo esse passado e um objetivo ligado diretamente "
                f"ao seu arquétipo: {conceito}. As primeiras decisões da jornada devem colocar essa identidade "
                "à prova, em vez de deixá-la apenas como uma descrição de ficha."
            )
        return {"atributos": atributos, "historia": hist}


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
                return await asyncio.wait_for(
                    asyncio.to_thread(worker),
                    timeout=self._request_timeout,
                )
            except asyncio.TimeoutError as exc:
                last_error = RuntimeError(
                    f"Timeout no provider {name} após {self._request_timeout:.0f}s"
                )
                self._cooldown_provider(name, last_error)
                log.warning("%s", last_error)
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
            payload["titulo"] = payload["aventura"]["titulo"]
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
        fallback["titulo"] = fallback["aventura"]["titulo"]
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
            "Crie somente uma história de personagem de D&D 5e 2014 em JSON com a chave 'historia'. "
            "Os atributos NÃO são definidos pela IA. Eles serão gerados separadamente pelo motor de regras "
            "usando 4d6, descartando o menor, seis vezes, e os bônus raciais oficiais. "
            "Não invente valores de atributos, bônus de classe ou regras fora de D&D 5e 2014. "
            "O campo 'Conceito e detalhes' é o ARQUÉTIPO CENTRAL do personagem e é obrigatório para a história. "
            "A história deve nascer desse arquétipo: mostre como ele moldou o passado, personalidade, hábitos, "
            "medos, objetivos, relações e dilemas do personagem. Não basta repetir ou citar o arquétipo no final. "
            "Transforme-o em acontecimentos concretos da vida do personagem e conecte-o organicamente à raça e classe. "
            "Não contradiga os detalhes do jogador, não troque raça/classe e não invente fatos que anulem o conceito. "
            "Escreva uma história com identidade suficiente para o Mestre conseguir usar o arquétipo durante a campanha. "
            f"Nome: {nome}. Raça: {raca}. Classe: {classe}. CONCEITO E ARQUÉTIPO CENTRAL: {detalhes or 'nenhum'}. "
            "Retorne somente JSON válido."
        )
        try:
            data = await self._request_json(prompt)
            if isinstance(data, dict):
                historia = str(data.get("historia") or "").strip()
                if historia:
                    try:
                        from .game.character_creation import gerar_atributos
                    except ImportError:
                        from game.character_creation import gerar_atributos
                    return {
                        "atributos": gerar_atributos(classe, raca),
                        "historia": historia[:4000],
                    }
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
        try:
            from .dice import detectar_atributo as _det
        except ImportError:
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

    @staticmethod
    def _validar_narrativa(data: dict, contexto_atual: str) -> dict:
        """Valida a resposta narrativa para impedir placeholders e contexto estagnado."""
        if not isinstance(data, dict):
            raise ValueError("Narrativa inválida: resposta não é objeto JSON")
        narrativa = str(data.get("narrativa") or "").strip()
        if not narrativa:
            raise ValueError("Narrativa vazia")
        contexto = str(data.get("novo_contexto") or "").strip()
        proibidos = (
            "a cena avança a partir dessa decisão",
            "a cena avança",
            "o narrador descreve o que acontece",
            "algo acontece",
            "a aventura continua",
        )
        texto_norm = Narrator._normalizar_acao(narrativa)
        if any(Narrator._normalizar_acao(p) in texto_norm for p in proibidos):
            raise ValueError("Narrativa genérica/placeholder rejeitada")
        if len(narrativa) < 60:
            raise ValueError("Narrativa curta demais para representar uma consequência")
        if not contexto or contexto.strip() == str(contexto_atual or "").strip():
            raise ValueError("Narrativa não produziu fato novo no contexto")
        sugestoes = data.get("sugestoes")
        if not isinstance(sugestoes, list):
            sugestoes = []
        return {
            "narrativa": narrativa[:6000],
            "novo_contexto": contexto[:4000],
            "sugestoes": sugestoes[:5],
        }

    def _fallback_narrativa(self, sessao: dict, personagem: dict, acao: str, teste: dict | None) -> dict:
        """Narrador offline com progressão de cena baseada no estado persistido."""
        contexto = str(sessao.get("contexto", "") or "").strip()
        aventura = sessao.get("aventura") or {}
        progresso = aventura.get("progresso") or {}
        locais = aventura.get("locais") or []
        local_id = progresso.get("local_atual")
        local = next((x for x in locais if x.get("id") == local_id), None)
        local_nome = (local or {}).get("nome") or "o local atual"
        nome = personagem.get("nome", "O personagem")
        texto = (acao or "").strip()
        n = self._normalizar_acao(texto)
        sucesso = bool(teste and teste.get("sucesso"))
        resultado_txt = "sucesso" if teste and sucesso else "falha" if teste else "sem teste"
        eventos = progresso.get("eventos_importantes") or []
        etapa = int(progresso.get("etapa_cena", 0) or 0)

        # Combate é resolvido pelo engine. O narrador apenas traduz o
        # resultado mecânico em ficção e não recalcula ataque, dano ou HP.
        if teste and teste.get("tipo") == "ataque":
            alvo = teste.get("alvo", "o alvo")
            dano = int(teste.get("dano", 0) or 0)
            hp_alvo = teste.get("hp_alvo", "?")
            if teste.get("critico"):
                narr = f"{nome} acerta {alvo} com um golpe crítico. O impacto causa {dano} de dano, deixando o inimigo com {hp_alvo} HP."
            elif teste.get("sucesso"):
                narr = f"{nome} atinge {alvo}. O golpe causa {dano} de dano, e o inimigo permanece com {hp_alvo} HP."
            elif teste.get("falha_critica"):
                narr = f"{nome} tenta atingir {alvo}, mas erra de forma desastrosa. Nenhum dano é causado."
            else:
                narr = f"{nome} desfere um ataque contra {alvo}, mas o golpe não encontra uma abertura. Nenhum dano é causado."
            evento = (
                f"{nome} atacou {alvo}: {'acerto' if teste.get('sucesso') else 'falha'}, "
                f"dano {dano}, HP do alvo {hp_alvo}."
            )
            sugestoes = ["Continuar o combate", "Mudar de posição", "Encerrar o turno"]

        # Movimento pela rota descoberta precisa produzir deslocamento real no fallback,
        # e nunca cair no texto genérico que apenas repete a cena.
        elif any(x in n for x in (
            "avancar", "avançar", "seguir pela", "seguir pelo",
            "avancar pela rota", "avançar pela rota",
            "descer", "subir", "atravessar", "cruzar", "aproximar",
            "afastar", "recuar", "retornar", "entrar", "sair",
            "continuar", "caminhar", "andar", "ir para", "ir pra",
            "vou para", "vou pra",
        )):
            proximos = [
                item for item in locais
                if item.get("id") in (local or {}).get("conexoes", [])
                and not item.get("descoberto")
            ]
            destino = proximos[0] if proximos else None
            if destino:
                destino_nome = destino.get("nome", "a próxima área")
                narr = (
                    f"{nome} avança pela rota descoberta e deixa {local_nome} para trás. "
                    f"O caminho conduz diretamente a {destino_nome}, onde o ambiente muda "
                    "e novos sinais mostram que a exploração está entrando em território ainda não examinado."
                )
                evento = f"{nome} avançou de {local_nome} para {destino_nome} pela rota descoberta."
                sugestoes = [
                    "Examinar o novo local",
                    "Observar os arredores antes de continuar",
                    "Seguir por outra passagem disponível",
                ]
            else:
                narr = (
                    f"{nome} avança pela rota que já conhece, mas não encontra uma nova saída imediata "
                    f"além de {local_nome}. O caminho termina por enquanto, e os sinais do local sugerem "
                    "que será preciso investigar o ambiente para descobrir a próxima passagem."
                )
                evento = f"{nome} tentou avançar pela rota descoberta, mas não havia nova conexão direta a explorar."
                sugestoes = [
                    "Examinar o local em busca de uma passagem",
                    "Observar sinais escondidos",
                    "Voltar pela rota conhecida",
                ]

        # Ações específicas consomem a pista anterior em vez de recomeçar a cena.
        elif any(x in n for x in ("rastrear", "seguir pegadas", "seguir as pegadas")):
            narr = (
                f"{nome} acompanha as pegadas sem perder o rastro. Elas atravessam a área externa "
                "e terminam junto ao acesso do local, onde a poeira foi removida recentemente. "
                "A pista deixa de ser apenas uma suspeita: alguém entrou por ali há pouco tempo."
            )
            evento = f"{nome} rastreou as pegadas e confirmou uma passagem recente pelo acesso."
            sugestoes = ["Entrar pela passagem", "Examinar o ponto onde as pegadas terminam", "Procurar sinais de quem passou por ali"]
        elif any(x in n for x in ("examinar", "investigar", "procurar", "buscar pistas", "inspecionar", "analisar")):
            if local_id == "area_interna" or etapa >= 2:
                narr = (
                    f"{nome} examina {local_nome} com mais cuidado. Atrás da camada de poeira, "
                    "surge uma escada estreita descendo para uma área mais profunda. O ar que sobe dali "
                    "é mais frio, e pequenas marcas recentes continuam pelos degraus."
                )
                evento = f"{nome} descobriu uma escada que leva da área interna para uma área mais profunda."
                sugestoes = ["Descer pela escada", "Examinar as marcas nos degraus", "Esperar e observar antes de descer"]
            else:
                prefixo = "Apesar da falha, " if teste and not sucesso else ""
                narr = (
                    f"{prefixo}{nome} examina cuidadosamente a região. A poeira interrompida revela "
                    "uma sequência de marcas recentes que passa pelo acesso e desaparece na área interna. "
                    "Agora existe uma direção concreta para seguir."
                )
                evento = f"{nome} examinou a pista e identificou a rota para a área interna."
                sugestoes = ["Entrar na área interna", "Seguir as marcas", "Examinar o acesso antes de entrar"]
        elif any(x in n for x in ("entrar", "acessar a parte interna", "acessar", "ir ate", "vou ate", "ir pra", "vou pra", "seguir para", "seguir pra")):
            if local_id == "area_interna":
                narr = (
                    f"{nome} já está dentro de {local_nome}. A passagem para a parte mais profunda "
                    "fica claramente visível agora, e os sinais recentes continuam por ela."
                )
                evento = f"{nome} confirmou a passagem da área interna para a área profunda."
                sugestoes = ["Seguir para a área profunda", "Examinar a passagem", "Ouvir antes de avançar"]
            else:
                narr = (
                    f"{nome} atravessa o acesso e entra na área interna. O ruído da tempestade fica mais distante, "
                    "e uma passagem estreita continua para dentro. As pegadas reaparecem no chão, agora muito mais nítidas."
                )
                evento = f"{nome} entrou na área interna e encontrou uma passagem que continua para dentro."
                sugestoes = ["Seguir pela passagem", "Examinar as pegadas", "Ouvir o que existe mais adiante"]
        elif any(x in n for x in ("ouvir", "escutar", "detectar", "perceber", "gritar", "tem alguem", "alguem ai")):
            if local_id == "area_profunda":
                narr = (
                    f"{nome} força a atenção sobre os sons da área profunda. O eco devolve o próprio chamado "
                    "com atraso, vindo de um ponto que não pode ser visto daqui. Não há resposta clara, mas agora "
                    "é possível afirmar que existe outro espaço além da passagem."
                )
                evento = f"{nome} ouviu um eco vindo de além da área profunda."
            elif teste and not sucesso:
                narr = (
                    f"{nome} tenta perceber uma resposta em meio ao ruído, mas não consegue identificar uma presença. "
                    "O chamado, porém, retorna pela passagem com um eco incomum, indicando que o interior é mais profundo "
                    "do que parecia."
                )
                evento = f"{nome} não identificou uma presença, mas confirmou que a passagem continua além do alcance da visão."
            else:
                narr = (
                    f"{nome} chama e aguça a atenção para a resposta. O som percorre a passagem e volta como um eco "
                    "curto vindo de uma área mais profunda. Ninguém responde, mas o ambiente claramente não termina aqui."
                )
                evento = f"{nome} ouviu um eco vindo de uma área mais profunda após chamar."
            sugestoes = ["Seguir em direção ao eco", "Avançar pela passagem", "Esperar por uma resposta"]
        elif any(x in n for x in ("olhar", "observar", "ver", "olho ao redor")):
            narr = (
                f"{nome} observa {local_nome} novamente, agora levando em conta o que já descobriu. "
                "A passagem e as marcas recentes continuam visíveis, mas um detalhe novo chama atenção: "
                "há sinais de uso muito mais recente perto do caminho que segue para dentro."
            )
            evento = f"{nome} reavaliou {local_nome} e confirmou sinais recentes no caminho de entrada."
            sugestoes = ["Seguir as marcas", "Entrar pela passagem", "Investigar os sinais de uso recente"]
        else:
            narr = (
                f"{nome} age em {local_nome}, e a situação muda sem apagar o que já foi descoberto. "
                f"A ação foi: {texto}. O resultado foi {resultado_txt}. A atenção agora se concentra "
                "na rota que continua além da área já explorada."
            )
            evento = f"{nome} realizou '{texto}' com {resultado_txt}; a exploração prossegue a partir das descobertas atuais."
            sugestoes = ["Avançar pela rota descoberta", "Examinar as pistas existentes", "Observar antes de agir"]

        novo_contexto = (
            f"{contexto}\n"
            f"Progressão: etapa {etapa + 1}. Evento: {evento} Resultado: {resultado_txt}."
        ).strip()
        return {"narrativa": narr, "novo_contexto": novo_contexto, "sugestoes": sugestoes}


    @staticmethod
    def _validar_intencao_semantica(data: dict, aventura: dict) -> dict:
        """Valida a classificação semântica sem dar autoridade mecânica à IA."""
        if not isinstance(data, dict):
            raise ValueError("Intenção semântica inválida")
        tipos = {
            "movimento", "percepcao", "investigacao", "obstaculo",
            "ferramentas", "furtividade", "furto", "social",
            "ataque", "narrativa", "fim_turno",
        }
        tipo = str(data.get("tipo") or "").strip().lower()
        if tipo not in tipos:
            raise ValueError("Tipo de intenção não permitido")

        destino = data.get("destino")
        if destino is not None:
            destino = str(destino).strip() or None
            ids = {str(local.get("id")) for local in (aventura.get("locais") or [])}
            if destino not in ids:
                destino = None

        habilidade = data.get("habilidade")
        if habilidade not in {
            "Acrobacia", "Adestrar Animais", "Arcanismo", "Atletismo",
            "Atuação", "Enganação", "Furtividade", "História", "Intuição",
            "Intimidação", "Investigação", "Medicina", "Natureza",
            "Percepção", "Persuasão", "Prestidigitação", "Religião",
            "Sobrevivência",
        }:
            habilidade = None

        return {
            "tipo": tipo,
            "alvo": str(data.get("alvo")).strip()[:120] if data.get("alvo") else None,
            "destino": destino,
            "habilidade": habilidade,
            "referencia": str(data.get("referencia") or "").strip()[:160],
        }

    async def interpretar_acao(self, sessao: dict, personagem: dict, acao: str) -> dict | None:
        """Traduz linguagem livre em intenção; não resolve nenhuma regra do jogo."""
        aventura = sessao.get("aventura") or {}
        locais = [
            {"id": local.get("id"), "nome": local.get("nome"), "descoberto": local.get("descoberto", False)}
            for local in aventura.get("locais", [])
        ]

        prompt = (
            "Você é o classificador semântico de um jogo de D&D. "
            "Entenda o OBJETIVO da frase do jogador, não apenas palavras isoladas. "
            "Retorne SOMENTE JSON válido com tipo, alvo, destino, habilidade e referencia. "
            "Tipos: movimento, percepcao, investigacao, obstaculo, ferramentas, furtividade, "
            "furto, social, ataque, narrativa, fim_turno. "
            "Movimento inclui qualquer intenção de mudar de posição ou continuar uma rota: "
            "ir, entrar, sair, voltar, avançar, continuar, seguir, pegar um caminho, tomar uma passagem, "
            "ir pela trilha, seguir as pegadas. Se o jogador não disser o nome formal de um local, destino é null "
            "e referencia descreve a rota/pista usada. "
            "NÃO narre, NÃO role dados, NÃO escolha CD, NÃO invente locais, NPCs, itens ou consequências. "
            f"Locais conhecidos: {json.dumps(locais, ensure_ascii=False)}. "
            f"Local atual: {(aventura.get('progresso') or {}).get('local_atual')}. "
            f"Quests: {json.dumps(aventura.get('quests') or [], ensure_ascii=False)[:5000]}. "
            f"Personagem: {personagem.get('nome')} ({personagem.get('classe')}, {personagem.get('raca')}). "
            f"Ação: {acao}"
        )
        try:
            data = await self._request_json(prompt)
            return self._validar_intencao_semantica(data, aventura)
        except Exception as exc:
            log.info("Classificador semântico indisponível; usando classificação local: %s", exc)

        # Fallback semântico local. Não tenta enumerar todos os verbos da língua:
        # identifica conceitos de intenção e deixa o motor validar a consequência.
        n = self._normalizar_acao(acao)
        if any(x in n for x in (
            "ir ", "vou ", "entrar", "entro", "sair", "voltar", "seguir",
            "avancar", "avançar", "continuar", "caminho", "rota", "passagem",
            "trilha", "pegadas", "corredor",
        )):
            return {
                "tipo": "movimento",
                "alvo": None,
                "destino": None,
                "habilidade": None,
                "referencia": acao[:160],
            }
        if any(x in n for x in ("atacar", "golpear", "bater em", "lutar contra")):
            return {
                "tipo": "ataque",
                "alvo": None,
                "destino": None,
                "habilidade": None,
                "referencia": acao[:160],
            }
        if any(x in n for x in ("ouvir", "escutar", "perceber", "detectar", "observar atentamente")):
            return {
                "tipo": "percepcao",
                "alvo": None,
                "destino": None,
                "habilidade": "Percepção",
                "referencia": acao[:160],
            }
        if any(x in n for x in ("investigar", "examinar", "inspecionar", "analisar", "procurar", "buscar pista")):
            return {
                "tipo": "investigacao",
                "alvo": None,
                "destino": None,
                "habilidade": "Investigação",
                "referencia": acao[:160],
            }
        if any(x in n for x in ("esconder", "ocultar", "furtividade", "me ocultar")):
            return {
                "tipo": "furtividade",
                "alvo": None,
                "destino": None,
                "habilidade": "Furtividade",
                "referencia": acao[:160],
            }
        if any(x in n for x in ("roubar", "furtar", "surrupiar", "pegar sem ser visto")):
            return {
                "tipo": "furto",
                "alvo": None,
                "destino": None,
                "habilidade": "Prestidigitação",
                "referencia": acao[:160],
            }
        return None

    async def narrar_acao_com_dado(self, sessao: dict, personagem: dict, jogadores: list, acao: str, teste: dict | None, historico: list | None = None) -> dict:
        historia = str(personagem.get("historia") or "").strip()
        prompt = (
            "Você é o Mestre de uma campanha de D&D. Resolva a ação do jogador como um acontecimento real "
            "dentro da cena, não como um comentário sobre a narrativa. Retorne JSON com as chaves "
            "'narrativa', 'novo_contexto' e 'sugestoes'. "
            "A narrativa DEVE produzir uma consequência concreta e observável nesta rodada. "
            "Pode ser uma reação de NPC, pista descoberta, mudança de posição, porta aberta/fechada, risco revelado, "
            "informação obtida, recurso perdido ou ganho, ou outra alteração compatível com o estado. "
            "Se a ação for social, descreva a reação de uma entidade existente. Se for exploração, revele um detalhe "
            "específico do ambiente. Se houver teste, respeite EXATAMENTE o sucesso ou falha fornecidos. "
            "Falha não significa ausência de narrativa: a tentativa deve produzir uma consequência compatível, sem transformar "
            "falha em sucesso. NUNCA use frases como 'a cena avança', 'algo acontece', 'o narrador descreve' ou 'a aventura continua'. "
            "NÃO repita a situação anterior sem acrescentar um fato novo. "
            "O novo_contexto deve registrar explicitamente o novo fato verdadeiro após a ação. "
            "Use somente entidades e fatos presentes no estado estruturado; não invente NPCs, itens ou locais para resolver uma ação. "
            "Se o jogador pedir para viajar para um destino que não existe como local conectado, não o teleporte: descreva a intenção "
            "de viagem e deixe claro que o caminho/destino ainda precisa ser descoberto ou validado. "
            "Ações de movimento como 'ir pra cidade' ou 'vou até a taverna' não devem receber teste de Inteligência apenas porque também contêm "
            "palavras como 'procurar'; movimento deve ser tratado como movimento quando o destino for conhecido ou como tentativa de viagem quando não for. "
            "O arquétipo do personagem deve influenciar a forma como ele percebe, reage e toma decisões, mas não deve criar bônus mecânicos inexistentes. "
            f"Contexto atual: {str(sessao.get('contexto', '') or '')[:4000]}. "
            f"Estado estruturado da aventura: {json.dumps(sessao.get('aventura') or {}, ensure_ascii=False)}. "
            f"Personagem ativo: {personagem.get('nome')} ({personagem.get('classe')}, {personagem.get('raca')}). "
            f"História/identidade do personagem: {historia[:4000]}. "
            f"Ação: {acao}. Teste e resultado mecânico: {teste}. "
            f"Jogadores presentes: {[p.get('nome') for p in (jogadores or [])]}. "
            f"Histórico recente: {(historico or [])[-10:]}. "
        )
        try:
            data = await self._request_json(prompt)
            if isinstance(data, dict):
                return self._validar_narrativa(data, sessao.get("contexto", ""))
        except Exception as exc:
            log.warning("Resposta narrativa rejeitada ou IA indisponível; usando fallback determinístico: %s", exc)

        return self._fallback_narrativa(sessao, personagem, acao, teste)

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
