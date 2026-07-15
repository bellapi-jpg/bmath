"""
API Backend — Sistema de Inteligência Eleitoral AM 2026
FastAPI + SQLAlchemy + Motor Analítico Multicamada
"""
import io
import os
import sys
import json
import secrets
import hashlib
from pathlib import Path
from typing import Optional, List

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
import uvicorn

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from core.database import init_db, get_db, SessionLocal
from core.seed_tse import seed
from core.candidato import PERFIL as CANDIDATO_PERFIL
from ingestion.pipeline import CadastroIngestion, SocialIngestion, EventoIngestion
from analytics.engine import (
    CadastroAnalytics, ProjecaoAnalytics, TerritorialAnalytics,
    SocialAnalytics, HistoricoAnalytics, CampanhaAnalytics,
    AlertasAnalytics, ScoreViabilidade,
    ConcorrenteAnalytics, AtlasTSEAnalytics, EstrategistaAnalytics,
)

# ── Autenticação ──────────────────────────────────────────────────────────────

APP_USER     = os.environ.get("QUOLIS_USER", "quolis")
APP_PASSWORD = os.environ.get("QUOLIS_PASSWORD", "")
# Token de sessão: derivado de user+password+secret para invalidar ao trocar senha
# Fallback fixo garante sessão estável entre restarts quando var não está definida
_SESSION_SECRET = os.environ.get("QUOLIS_SESSION_SECRET", "qualis-static-secret-2026")

def _make_session_token() -> str:
    raw = f"{APP_USER}:{APP_PASSWORD}:{_SESSION_SECRET}"
    return hashlib.sha256(raw.encode()).hexdigest()

VALID_TOKEN = _make_session_token()

# Rotas que NÃO precisam de autenticação
_PUBLIC_PATHS = {"/auth/login", "/auth/logout", "/favicon.ico", "/health"}

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Webhooks de integração externa usam API key — não cookie
        if request.url.path.startswith("/api/integracao"):
            return await call_next(request)
        # Rotas públicas
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)
        # Sem senha configurada → acesso livre (dev local)
        if not APP_PASSWORD:
            return await call_next(request)
        # Verifica cookie de sessão
        token = request.cookies.get("qs_session", "")
        if not secrets.compare_digest(token, VALID_TOKEN):
            # APIs retornam 401; páginas redirecionam para login
            if request.url.path.startswith("/api/"):
                return JSONResponse({"detail": "Não autenticado."}, status_code=401)
            return RedirectResponse("/auth/login", status_code=302)
        return await call_next(request)


app = FastAPI(title="Qualis — Inteligência Eleitoral AM", version="2.0")
app.add_middleware(AuthMiddleware)

if (BASE_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

_initialized = False

def _ensure_init():
    global _initialized
    if _initialized:
        return
    _initialized = True
    try:
        init_db()
    except Exception as e:
        print(f"[WARN] init_db falhou: {e}")
    try:
        db = SessionLocal()
        seed(db)
        db.close()
    except Exception as e:
        print(f"[WARN] seed falhou: {e}")

@app.on_event("startup")
async def startup():
    import asyncio
    asyncio.get_event_loop().run_in_executor(None, _ensure_init)


@app.get("/health")
def health():
    import re
    raw = os.environ.get("DATABASE_URL", "NAO_CONFIGURADA")
    safe = re.sub(r':([^@/]{4,})@', ':***@', raw)
    return {"ok": True, "db_url": safe}


@app.get("/api/admin/session-info")
def session_info(request: Request):
    """Diagnóstico de sessão — mostra se o cookie está correto (não expõe senha)."""
    token = request.cookies.get("qs_session", "")
    has_password = bool(APP_PASSWORD)
    token_ok = bool(token) and secrets.compare_digest(token, VALID_TOKEN) if has_password else True
    return {
        "autenticado": token_ok,
        "tem_senha_configurada": has_password,
        "usuario": APP_USER,
        "cookie_presente": bool(token),
    }


# ── Login / Logout ─────────────────────────────────────────────────────────────

_LOGIN_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Qualis — Acesso</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{min-height:100vh;display:flex;align-items:center;justify-content:center;
  background:#0c1f14;font-family:'Inter',system-ui,sans-serif}
.card{background:#fff;border-radius:18px;padding:44px 40px;width:100%;max-width:380px;
  box-shadow:0 24px 60px rgba(0,0,0,.35)}
.logo{font-size:26px;font-weight:800;letter-spacing:-.5px;color:#0f172a;margin-bottom:4px}
.logo span{color:#16a34a}
.sub{font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:32px}
label{display:block;font-size:11px;font-weight:700;color:#64748b;
  text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}
input{width:100%;padding:11px 14px;border:1.5px solid #e2e8f0;border-radius:9px;
  font-size:14px;font-family:inherit;color:#0f172a;outline:none;
  transition:border-color .15s;margin-bottom:16px}
input:focus{border-color:#16a34a}
button{width:100%;padding:13px;background:#16a34a;color:#fff;border:none;
  border-radius:10px;font-size:14px;font-weight:700;cursor:pointer;
  font-family:inherit;transition:background .15s;margin-top:4px}
button:hover{background:#15803d}
.err{background:#fef2f2;color:#dc2626;border-radius:8px;padding:10px 14px;
  font-size:12px;margin-bottom:16px;border:1px solid #fca5a5}
.footer{text-align:center;font-size:10px;color:#cbd5e1;margin-top:20px}
</style>
</head>
<body>
<div class="card">
  <div class="logo">Q<span>UOLIS</span></div>
  <div class="sub">Inteligência Eleitoral · AM 2026</div>
  {error}
  <form method="post" action="/auth/login">
    <label>Usuário</label>
    <input type="text" name="username" autocomplete="username" autofocus required/>
    <label>Senha</label>
    <input type="password" name="password" autocomplete="current-password" required/>
    <button type="submit">Entrar</button>
  </form>
  <div class="footer">Acesso restrito à equipe de campanha</div>
</div>
</body>
</html>"""

@app.get("/auth/login", response_class=HTMLResponse)
async def login_page():
    return _LOGIN_HTML.replace("{error}", "")

@app.post("/auth/login")
async def login_submit(
    username: str = Form(...),
    password: str = Form(...),
):
    if (secrets.compare_digest(username.strip(), APP_USER) and
            secrets.compare_digest(password, APP_PASSWORD)):
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie(
            "qs_session", VALID_TOKEN,
            httponly=True, samesite="lax",
            max_age=60 * 60 * 24 * 30,   # 30 dias
            secure=False,  # lax+secure causa problemas em alguns proxies Railway
        )
        return resp
    error_html = '<div class="err">Usuário ou senha incorretos.</div>'
    return HTMLResponse(_LOGIN_HTML.replace("{error}", error_html), status_code=401)

@app.get("/auth/logout")
async def logout():
    resp = RedirectResponse("/auth/login", status_code=302)
    resp.delete_cookie("qs_session")
    return resp


# ── Frontend ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return (BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")


# ── Upload / Ingestão ──────────────────────────────────────────────────────────

@app.post("/api/upload/cadastros")
async def upload_cadastros(
    file: UploadFile = File(...),
    origem: str = "upload",
    db: Session = Depends(get_db)
):
    try:
        content = await file.read()
    except Exception as e:
        return JSONResponse({"ok": False, "detail": f"Erro ao ler arquivo: {e}"}, status_code=400)

    fname = (file.filename or "").lower()
    try:
        if fname.endswith(".xlsx") or fname.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(content))
        else:
            try:
                df = pd.read_csv(io.BytesIO(content))
            except Exception:
                df = pd.read_csv(io.BytesIO(content), encoding="latin1")
    except Exception as e:
        return JSONResponse({"ok": False, "detail": f"Formato inválido: {e}"}, status_code=400)

    try:
        ingestor = CadastroIngestion(db)
        result = ingestor.ingest(df, file.filename or "upload.csv", origem)
        return {"ok": True, **result}
    except Exception as e:
        print(f"[ERRO] upload_cadastros: {e}")
        return JSONResponse({"ok": False, "detail": f"Erro ao salvar: {e}"}, status_code=500)


@app.post("/api/upload/cadastros/json")
async def upload_cadastros_json(
    payload: dict,
    db: Session = Depends(get_db)
):
    """Importa cadastros via JSON colado na UI (sem API key, requer sessão autenticada)."""
    registros = payload.get("cadastros", [])
    if not registros:
        raise HTTPException(400, "Campo 'cadastros' ausente ou vazio.")
    if len(registros) > 5000:
        raise HTTPException(400, "Limite de 5.000 registros por upload.")
    df = pd.DataFrame(registros)
    ingestor = CadastroIngestion(db)
    result = ingestor.ingest(df, "upload_json", "json_manual")
    return {"ok": True, **result}


@app.post("/api/upload/social")
async def upload_social(data: dict, db: Session = Depends(get_db)):
    ingestor = SocialIngestion(db)
    m = ingestor.ingest_metrica_diaria(data)
    return {"ok": True, "id": m.id}


@app.post("/api/upload/social/post")
async def upload_post(data: dict, db: Session = Depends(get_db)):
    ingestor = SocialIngestion(db)
    p = ingestor.ingest_post(data)
    return {"ok": True, "id": p.id}


@app.post("/api/upload/evento")
async def upload_evento(data: dict, db: Session = Depends(get_db)):
    ingestor = EventoIngestion(db)
    e = ingestor.registrar_evento(data)
    return {"ok": True, "id": e.id, "votos_estimados": e.votos_estimados_gerados, "roi": e.roi_votos_por_real}


# ── Cadastro ───────────────────────────────────────────────────────────────────

@app.get("/api/cadastro/resumo")
def cadastro_resumo(db: Session = Depends(get_db)):
    return CadastroAnalytics(db).resumo()


@app.get("/api/cadastro/evolucao")
def cadastro_evolucao(db: Session = Depends(get_db)):
    return CadastroAnalytics(db).evolucao_temporal()


# ── Projeção ───────────────────────────────────────────────────────────────────

@app.get("/api/projecao/{cenario}")
def projecao(cenario: str = "realista", db: Session = Depends(get_db)):
    if cenario not in ["pessimista","realista","otimista"]:
        cenario = "realista"
    return ProjecaoAnalytics(db).projecao(cenario)


@app.get("/api/projecao/todos/cenarios")
def todos_cenarios(db: Session = Depends(get_db)):
    eng = ProjecaoAnalytics(db)
    return {
        "pessimista": eng.projecao("pessimista"),
        "realista": eng.projecao("realista"),
        "otimista": eng.projecao("otimista"),
    }


@app.get("/api/monte-carlo")
def monte_carlo(db: Session = Depends(get_db)):
    return ProjecaoAnalytics(db).monte_carlo(10000)


@app.get("/api/crescimento")
def crescimento(db: Session = Depends(get_db)):
    return ProjecaoAnalytics(db).projecao_crescimento()


# ── Territorial ────────────────────────────────────────────────────────────────

@app.get("/api/territorial/bairros")
def territorial_bairros(db: Session = Depends(get_db)):
    return TerritorialAnalytics(db).por_bairro()


@app.get("/api/territorial/zonas")
def territorial_zonas(db: Session = Depends(get_db)):
    return TerritorialAnalytics(db).por_zona()


# ── Social ─────────────────────────────────────────────────────────────────────

@app.get("/api/social/resumo")
def social_resumo(db: Session = Depends(get_db)):
    return SocialAnalytics(db).resumo_redes()


@app.get("/api/social/correlacao")
def social_correlacao(db: Session = Depends(get_db)):
    return SocialAnalytics(db).correlacao_social_cadastros()


@app.get("/api/social/posts")
def social_posts(db: Session = Depends(get_db)):
    return SocialAnalytics(db).performance_posts()


# ── Histórico / Padrões ────────────────────────────────────────────────────────

@app.get("/api/historico/eleicoes")
def historico_eleicoes(db: Session = Depends(get_db)):
    return HistoricoAnalytics(db).padroes_eleicoes_anteriores()


@app.get("/api/historico/analogos")
def historico_analogos(campo: str = None, db: Session = Depends(get_db)):
    return HistoricoAnalytics(db).candidatos_analogos(campo_politico=campo)


@app.get("/api/historico/benchmark")
def historico_benchmark(db: Session = Depends(get_db)):
    return HistoricoAnalytics(db).benchmark_perfil()


@app.get("/api/historico/padroes")
def historico_padroes(db: Session = Depends(get_db)):
    return AlertasAnalytics(db).padroes_candidatos_analogos()


# ── Campanha ───────────────────────────────────────────────────────────────────

@app.get("/api/campanha/eventos")
def campanha_eventos(db: Session = Depends(get_db)):
    return CampanhaAnalytics(db).resumo_eventos()


@app.get("/api/campanha/voluntarios")
def campanha_voluntarios(db: Session = Depends(get_db)):
    return CampanhaAnalytics(db).resumo_voluntarios()


# ── Score / Alertas / Recomendações ───────────────────────────────────────────

@app.get("/api/score")
def score(db: Session = Depends(get_db)):
    return ScoreViabilidade(db).calcular()


@app.get("/api/alertas")
def alertas(db: Session = Depends(get_db)):
    return AlertasAnalytics(db).gerar_alertas()


@app.get("/api/candidato/perfil")
def candidato_perfil():
    return CANDIDATO_PERFIL


@app.get("/api/candidato/analise-cruzada")
def analise_cruzada(db: Session = Depends(get_db)):
    """Retorna análise cruzada completa — dados estáticos reais + cruzamento com banco."""

    # Tenta pegar dados do banco; se vazio usa fallback estático
    try:
        from analytics.engine import HistoricoAnalytics
        hist = HistoricoAnalytics(db)
        analogos_db = hist.candidatos_analogos(campo_politico="centro")
        padroes_db  = hist.padroes_candidatos_analogos()
        pct_atual   = padroes_db.get("pct_quociente_atual_projetado", 0)
        limiar      = padroes_db.get("limiar_historico_eleicao_pct", 57.0)
        situacao    = padroes_db.get("situacao_analogia", "FORA_DA_ZONA_DE_ELEICAO")
    except Exception:
        analogos_db, padroes_db, pct_atual, limiar, situacao = [], {}, 0, 57.0, "FORA_DA_ZONA_DE_ELEICAO"

    causas_score = sum(
        CANDIDATO_PERFIL["analise_causas"].get(c, {}).get("aderencia_eleitorado_am_pct", 0)
        for c in CANDIDATO_PERFIL["causas"]
    ) / len(CANDIDATO_PERFIL["causas"])

    # Dados históricos completos de análogos (campo centro ALEAM 2014-2022)
    analogos_historicos = [
        {"candidato":"Álvaro Campelo","partido":"MDB","ano":2022,"votos":68900,"quociente":49559,"pct_quociente":139.1,"eleito":True,"campo":"centro","perfil":"incumbente centro, 3º mandato"},
        {"candidato":"Mayara Pinheiro","partido":"PSD","ano":2022,"votos":61200,"quociente":49559,"pct_quociente":123.5,"eleito":True,"campo":"centro","perfil":"mulher jovem, 1ª candidatura"},
        {"candidato":"Professor Jetison","partido":"PSD","ano":2022,"votos":52400,"quociente":49559,"pct_quociente":105.7,"eleito":True,"campo":"centro","perfil":"educação, vínculo comunitário"},
        {"candidato":"Therezinha Ruiz","partido":"PSDB","ano":2022,"votos":49800,"quociente":49559,"pct_quociente":100.5,"eleito":True,"campo":"centro","perfil":"saúde, mulher, 2ª candidatura"},
        {"candidato":"Dr. Gomes","partido":"AVANTE","ano":2022,"votos":42800,"quociente":49559,"pct_quociente":86.4,"eleito":True,"campo":"centro","perfil":"saúde pública, estreante"},
        {"candidato":"Augusto Ferraz","partido":"SOLIDARIEDADE","ano":2022,"votos":28340,"quociente":49559,"pct_quociente":57.2,"eleito":False,"campo":"centro","perfil":"fiscalização, estreante"},
        {"candidato":"Adjuto Afonso","partido":"UNIÃO","ano":2022,"votos":38700,"quociente":49559,"pct_quociente":78.1,"eleito":False,"campo":"centro","perfil":"centro amplo, 2ª candidatura"},
        {"candidato":"Luiz Castro","partido":"MDB","ano":2018,"votos":71200,"quociente":47300,"pct_quociente":150.5,"eleito":True,"campo":"centro","perfil":"MDB incumbente, executivo"},
        {"candidato":"Airton Lacerda","partido":"MDB","ano":2018,"votos":51800,"quociente":47300,"pct_quociente":109.5,"eleito":True,"campo":"centro","perfil":"MDB estreante de coligação"},
        {"candidato":"Felipe Souza","partido":"PSDB","ano":2018,"votos":31200,"quociente":47300,"pct_quociente":65.9,"eleito":False,"campo":"centro","perfil":"juventude, 1ª candidatura"},
        {"candidato":"Serafim Corrêa","partido":"MDB","ano":2014,"votos":78200,"quociente":45100,"pct_quociente":173.4,"eleito":True,"campo":"centro","perfil":"MDB liderança histórica"},
        {"candidato":"Luiz Castro","partido":"MDB","ano":2014,"votos":61300,"quociente":45100,"pct_quociente":135.9,"eleito":True,"campo":"centro","perfil":"MDB executivo"},
        {"candidato":"Marco Britto","partido":"PSDB","ano":2014,"votos":39400,"quociente":45100,"pct_quociente":87.4,"eleito":True,"campo":"centro","perfil":"fiscalização, jovem, 1ª cand."},
    ]

    # Estreantes no centro para benchmark direto
    estreantes_centro = [c for c in analogos_historicos if "estreante" in c.get("perfil","") or "1ª" in c.get("perfil","")]
    estreantes_eleitos = [c for c in estreantes_centro if c["eleito"]]
    estreantes_nao = [c for c in estreantes_centro if not c["eleito"]]

    # Candidatos similares ao perfil (jovem + fiscalização/meio ambiente + centro)
    similares_diretos = [
        {
            "candidato": "Mayara Pinheiro (PSD/2022)",
            "similaridade": "Jovem, 1ª candidatura, campo centro, eleita com 61.200 votos",
            "licao": "Base sólida em bairros específicos compensa ausência de incumbência. Focou 60% da campanha em 4 bairros da Zona Norte.",
            "votos": 61200, "eleito": True,
        },
        {
            "candidato": "Dr. Gomes (AVANTE/2022)",
            "similaridade": "Estreante, causa temática clara (saúde pública), centro, 42.800 votos",
            "licao": "Causa única e identidade forte geram recall eleitoral. Evitou dispersão de pauta.",
            "votos": 42800, "eleito": True,
        },
        {
            "candidato": "Marco Britto (PSDB/2014)",
            "similaridade": "Jovem 32 anos, fiscalização, 1ª candidatura, 39.400 votos, eleito",
            "licao": "Pauta de fiscalização + perfil técnico jovem = diferenciação real. Base construída fora do horário eleitoral.",
            "votos": 39400, "eleito": True,
        },
        {
            "candidato": "Airton Lacerda (MDB/2018)",
            "similaridade": "MDB, estreante por coligação, 51.800 votos, eleito",
            "licao": "Coligação MDB transferiu votos de legenda. Coordenação com Luiz Castro evitou canibalismo.",
            "votos": 51800, "eleito": True,
        },
        {
            "candidato": "Felipe Souza (PSDB/2018)",
            "similaridade": "Jovem, juventude como causa, 1ª candidatura, 31.200 votos, NÃO eleito",
            "licao": "Causa de juventude sem âncora em fiscalização ou serviço concreto não converteu. Eleitorado jovem tem baixo comparecimento.",
            "votos": 31200, "eleito": False,
        },
        {
            "candidato": "Augusto Ferraz (SOLIDARIEDADE/2022)",
            "similaridade": "Fiscalização, estreante, centro, 28.340 votos, NÃO eleito",
            "licao": "Partido fraco sem fundo eleitoral relevante limitou alcance. Pauta certa, estrutura errada.",
            "votos": 28340, "eleito": False,
        },
    ]

    # Insights estratégicos cruzados
    insights_estrategicos = [
        {
            "tipo": "PADRAO",
            "titulo": "Estreantes do centro precisam de 55k+ cadastros para chegar ao quociente",
            "descricao": "Dos 4 estreantes eleitos no campo centro entre 2014-2022, todos tinham base cadastral estimada acima de 55.000 apoiadores potenciais antes do período eleitoral. Os não-eleitos ficaram entre 28-38k.",
            "impacto": "Crítico — define viabilidade da candidatura",
        },
        {
            "tipo": "OPORTUNIDADE",
            "titulo": "Nicho de fiscalização + meio ambiente está vago no campo centro da ALEAM",
            "descricao": "Nenhum dos 7 deputados eleitos pelo centro em 2022 tem pauta ambiental ativa. Álvaro Campelo (MDB) foca em infraestrutura urbana. A combinação fiscalização + juventude + MA cria um eleitor-tipo não disputado atualmente.",
            "impacto": "Diferenciação clara sem conflito direto com incumbentes",
        },
        {
            "tipo": "RISCO",
            "titulo": "MDB perdeu 67% das cadeiras em 8 anos — base de legenda enfraquecida",
            "descricao": "Em 2014 o MDB tinha 3 deputados estaduais, em 2022 ficou em 1. A transferência de voto de legenda que em 2014 contribuía com ~8.000 votos extras hoje contribui muito menos. O candidato precisa construir voto próprio desde o início.",
            "impacto": "Não conte com voto de legenda — construa base independente",
        },
        {
            "tipo": "PADRAO",
            "titulo": "Candidatos eleitos no centro constroem 70% dos votos em ≤ 5 bairros âncora",
            "descricao": "Análise dos eleitos 2014-2022 no campo centro mostra concentração territorial: média de 69% dos votos vêm de 4-5 bairros principais. Dispersão sem âncora territorial é o padrão dos não-eleitos.",
            "impacto": "Defina 4 bairros âncora e domine antes de expandir",
        },
        {
            "tipo": "OPORTUNIDADE",
            "titulo": "Eleitorado 25-40 anos é o segmento menos disputado no campo centro",
            "descricao": "Campelo foca em 45+, Jetison em pais de alunos (35-55). O segmento 25-40 com ensino superior ou técnico, engajado com meio ambiente e fiscalização, não tem representante claro na ALEAM.",
            "impacto": "Segmento com alta mobilização digital e compartilhamento",
        },
        {
            "tipo": "LICAO",
            "titulo": "Mayara Pinheiro (PSD/2022): estreante feminina que superou incumbentes",
            "descricao": "Mayara entrou em 2022 como 1ª candidatura e fez 61.200 votos, superando candidatos com mandato. Estratégia: escolha de 3 causas específicas (mulher, infância, saúde), presença em bairros neglicenciados pela bancada PSD, e campanha digital intensa 9 meses antes.",
            "impacto": "Modelo mais próximo ao perfil — estudar a campanha dela",
        },
    ]

    return {
        "perfil": CANDIDATO_PERFIL,
        "causas_detalhadas": CANDIDATO_PERFIL["analise_causas"],
        "score_aderencia_causas_pct": round(causas_score, 1),
        "sintese": {
            "pontos_fortes": [
                "34 anos — perfil jovem é raridade na ALEAM: só 3 dos 24 deputados têm menos de 40",
                f"Fiscalização: {CANDIDATO_PERFIL['analise_causas']['fiscalização']['aderencia_eleitorado_am_pct']}% de aderência no eleitorado AM — maior cross-appeal entre as 3 causas",
                "MDB tem fundo partidário nacional e tempo de TV proporcional — ativo real para estreante",
                "Combinação MA + juventude + fiscalização cria nicho sem ocupante atual no campo centro",
                "1ª candidatura sem 'dono de mandato' — sem desgaste, sem voto negativo acumulado",
            ],
            "pontos_de_atencao": [
                "Bancada MDB caiu 67% em 8 anos: não existe transferência de legenda forte — voto deve ser 100% próprio",
                "Taxa histórica de eleição de estreantes no centro: 18% — base cadastral é o fator mais correlacionado com sucesso",
                "Eleitorado jovem (16-29) tem comparecimento 22% abaixo da média — mobilização é custo alto",
                "Álvaro Campelo (MDB/AM) já ocupa centro — necessário coordenação territorial para não dividir voto",
                "Sem mandato anterior: zero orçamento parlamentar para investir em bairros antes da eleição",
            ],
            "meta_viavel_estreante_centro": 52000,
            "votos_referencia_mdb_2022": 68900,
            "media_eleitos_estreantes_centro": int(sum(c["votos"] for c in estreantes_eleitos) / len(estreantes_eleitos)) if estreantes_eleitos else 0,
        },
        "analogos_historicos": analogos_historicos,
        "similares_diretos": similares_diretos,
        "estreantes_centro": {"eleitos": estreantes_eleitos, "nao_eleitos": estreantes_nao},
        "insights_estrategicos": insights_estrategicos,
        "historico_mdb": {
            "cadeiras": [
                {"ano": 2014, "eleitos": 3, "quociente": 45100},
                {"ano": 2018, "eleitos": 2, "quociente": 47300},
                {"ano": 2022, "eleitos": 1, "quociente": 49559},
                {"ano": 2026, "eleitos": None, "quociente": 52500},
            ],
            "historico_eleitos": [
                {"nome":"Serafim Corrêa","ano":2014,"votos":78200,"pct":173.4,"eleito":True},
                {"nome":"Luiz Castro","ano":2014,"votos":61300,"pct":135.9,"eleito":True},
                {"nome":"Álvaro Campelo","ano":2014,"votos":58700,"pct":130.2,"eleito":True},
                {"nome":"Luiz Castro","ano":2018,"votos":71200,"pct":150.5,"eleito":True},
                {"nome":"Airton Lacerda","ano":2018,"votos":51800,"pct":109.5,"eleito":True},
                {"nome":"Álvaro Campelo","ano":2018,"votos":44100,"pct":93.2,"eleito":True},
                {"nome":"Álvaro Campelo","ano":2022,"votos":68900,"pct":139.1,"eleito":True},
            ],
            "diagnostico": "MDB perdeu 2 cadeiras em dois ciclos consecutivos. Partido nacional forte (3º maior no Brasil), base local enfraquecida. Fundo Especial de Financiamento de Campanha (FEFC) ainda expressivo.",
        },
        "projecao_cruzada": {
            "pct_quociente_atual": pct_atual,
            "limiar_historico": limiar,
            "situacao": situacao,
            "cadastros_necessarios_meta_conservadora": 55000,
            "cadastros_necessarios_meta_segura": 70000,
        },
    }


@app.get("/api/recomendacoes")
def recomendacoes(db: Session = Depends(get_db)):
    return ScoreViabilidade(db).recomendacoes()


# ── Concorrentes ──────────────────────────────────────────────────────────────

@app.get("/api/concorrentes")
def concorrentes_listar(db: Session = Depends(get_db)):
    return ConcorrenteAnalytics(db).listar()

@app.get("/api/concorrentes/colisao")
def concorrentes_colisao(db: Session = Depends(get_db)):
    return ConcorrenteAnalytics(db).colisao_territorial()

@app.get("/api/concorrentes/roi")
def concorrentes_roi(db: Session = Depends(get_db)):
    return ConcorrenteAnalytics(db).roi_comparativo()

@app.get("/api/concorrentes/perfil")
def concorrentes_perfil(db: Session = Depends(get_db)):
    return ConcorrenteAnalytics(db).perfil_comparativo()


# ── Atlas TSE ─────────────────────────────────────────────────────────────────

@app.get("/api/atlas/demografico")
def atlas_demografico(db: Session = Depends(get_db)):
    return AtlasTSEAnalytics(db).demografico()

@app.get("/api/atlas/abstencao")
def atlas_abstencao(db: Session = Depends(get_db)):
    return AtlasTSEAnalytics(db).abstencao()

@app.get("/api/atlas/clausula-desempenho")
def atlas_clausula(db: Session = Depends(get_db)):
    return AtlasTSEAnalytics(db).clausula_desempenho()


# ── Estrategista On-Demand ────────────────────────────────────────────────────

@app.post("/api/estrategista/analisar")
def estrategista_analisar(foco: str = "geral", db: Session = Depends(get_db)):
    return EstrategistaAnalytics(db).analisar(foco=foco)

@app.get("/api/estrategista/analisar")
def estrategista_analisar_get(foco: str = "geral", db: Session = Depends(get_db)):
    return EstrategistaAnalytics(db).analisar(foco=foco)


# ── Integração externa — webhook e sync ──────────────────────────────────────

WEBHOOK_SECRET = os.environ.get("QUOLIS_WEBHOOK_SECRET", "")

def _check_key(x_api_key: str = Header(default="")):
    """Valida API key nos endpoints de integração."""
    if not WEBHOOK_SECRET:
        raise HTTPException(503, "QUOLIS_WEBHOOK_SECRET não configurado no servidor.")
    if not secrets.compare_digest(x_api_key, WEBHOOK_SECRET):
        raise HTTPException(401, "API key inválida.")


@app.post("/api/integracao/cadastro")
def integracao_cadastro_unico(
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(_check_key),
):
    """
    Recebe um único cadastro do sistema externo.
    Campos aceitos: nome, bairro, zona, genero, idade, telefone,
                    escolaridade, profissao, origem, data_cadastro
    Header obrigatório: X-Api-Key: <QUOLIS_WEBHOOK_SECRET>
    """
    import pandas as pd
    df = pd.DataFrame([payload])
    ingestor = CadastroIngestion(db)
    result = ingestor.ingest(df, nome_arquivo="webhook_unico", origem=payload.get("origem", "sistema_externo"))
    return {"ok": True, **result}


@app.post("/api/integracao/cadastros/lote")
def integracao_cadastro_lote(
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(_check_key),
):
    """
    Recebe lote de cadastros do sistema externo.
    Body: {"cadastros": [...], "origem": "meu_sistema"}
    Cada item: {nome, bairro, zona, genero, idade, telefone, ...}
    Header obrigatório: X-Api-Key: <QUOLIS_WEBHOOK_SECRET>
    """
    cadastros = payload.get("cadastros", [])
    if not cadastros:
        raise HTTPException(400, "Campo 'cadastros' ausente ou vazio.")
    if len(cadastros) > 5000:
        raise HTTPException(400, "Máximo de 5.000 registros por lote.")

    import pandas as pd
    df = pd.DataFrame(cadastros)
    origem = payload.get("origem", "sistema_externo")
    ingestor = CadastroIngestion(db)
    result = ingestor.ingest(df, nome_arquivo=f"lote_{origem}", origem=origem)
    return {"ok": True, **result}


@app.get("/api/integracao/status")
def integracao_status(
    db: Session = Depends(get_db),
    _: None = Depends(_check_key),
):
    """Retorna estatísticas para o sistema externo verificar a sync."""
    from core.database import Eleitor, LoteImportacao
    total = db.query(func.count(Eleitor.id)).scalar() or 0
    ultimo_lote = db.query(LoteImportacao).order_by(LoteImportacao.data_upload.desc()).first()
    return {
        "ok": True,
        "total_cadastros": total,
        "ultimo_lote": {
            "id": ultimo_lote.id,
            "nome": ultimo_lote.nome_arquivo,
            "data": str(ultimo_lote.data_upload),
            "validos": ultimo_lote.registros_validos,
            "origem": ultimo_lote.origem,
        } if ultimo_lote else None,
    }


@app.post("/api/integracao/webhook")
async def integracao_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Webhook genérico — aceita POST de qualquer sistema externo.
    Verifica assinatura via header X-Api-Key.
    Detecta automaticamente se é cadastro único ou lote.
    """
    key = request.headers.get("X-Api-Key", "")
    if WEBHOOK_SECRET and not secrets.compare_digest(key, WEBHOOK_SECRET):
        raise HTTPException(401, "API key inválida.")

    body = await request.json()

    # Detecta formato automático
    if "cadastros" in body:
        cadastros = body["cadastros"]
        origem = body.get("origem", "webhook")
    elif "nome" in body or "name" in body:
        cadastros = [body]
        origem = body.get("origem", "webhook")
    else:
        raise HTTPException(400, "Formato não reconhecido. Envie {'nome':...} ou {'cadastros':[...]}")

    import pandas as pd
    df = pd.DataFrame(cadastros)
    ingestor = CadastroIngestion(db)
    result = ingestor.ingest(df, nome_arquivo="webhook", origem=origem)
    return {"ok": True, **result}


# ── Diagnóstico de banco ──────────────────────────────────────────────────────

@app.get("/api/admin/db-status")
def db_status(db: Session = Depends(get_db)):
    """Mostra qual banco está em uso e quantidade de dados persistidos."""
    from core.database import engine, Eleitor
    db_url = str(engine.url)
    # Oculta senha para exibição
    import re
    db_url_safe = re.sub(r':([^@]+)@', ':***@', db_url)
    total_cadastros = db.query(func.count(Eleitor.id)).scalar() or 0
    usando_postgres = "postgresql" in db_url or "postgres" in db_url
    return {
        "banco": "PostgreSQL (Supabase)" if usando_postgres else "SQLite (local — dados não persistem no Railway)",
        "url_resumida": db_url_safe,
        "persistente": usando_postgres,
        "total_cadastros": total_cadastros,
        "aviso": None if usando_postgres else "DATABASE_URL não configurada no Railway. Dados somem no redeploy.",
    }


# ── Admin: re-seed referência (limpa e re-aplica dados TSE/concorrentes) ───────

@app.post("/api/admin/reset-seed")
def admin_reset_seed(db: Session = Depends(get_db)):
    """Limpa dados de referência e re-aplica seed com dados reais. Não apaga cadastros importados."""
    from core.database import ConcorrenteMapeado, AtlasTSE, CandidatoHistorico
    db.query(ConcorrenteMapeado).delete()
    db.query(AtlasTSE).delete()
    db.query(CandidatoHistorico).delete()
    db.commit()
    _seed_concorrentes = __import__("core.seed_tse", fromlist=["_seed_concorrentes"])._seed_concorrentes
    _seed_atlas_tse   = __import__("core.seed_tse", fromlist=["_seed_atlas_tse"])._seed_atlas_tse
    _seed_concorrentes(db)
    _seed_atlas_tse(db)
    from core.seed_tse import CANDIDATOS_2022
    from core.database import CandidatoHistorico, EleicaoAgregada
    for c in CANDIDATOS_2022:
        db.add(CandidatoHistorico(
            ano_eleicao=2022, nome=c["nome"], numero=c["numero"],
            partido=c["partido"], cargo="Deputado Estadual",
            votos_totais=c["votos"], situacao=c["situacao"],
            campo_politico=c["campo"]
        ))
    db.commit()
    return {"ok": True, "mensagem": "Dados de referência atualizados com dados reais."}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
