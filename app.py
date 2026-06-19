"""
API Backend - Sistema de Projeção Eleitoral
Deputado Estadual Amazonas 2026
"""
import json
import os
import io
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from analytics_engine import ElectoralAnalytics
from tse_reference import (
    ZONAS_MANAUS, PERFIL_ELEITORADO_AM, HISTORICO_ALEAM,
    PROJECAO_2026, PADROES_COMPORTAMENTAIS, BAIRROS_MANAUS
)

app = FastAPI(title="Sistema Eleitoral AM", version="1.0")

BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "uploads" / "cadastros.csv"

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# ── Cache em memória ───────────────────────────────────────────────────────────
_df_cache: Optional[pd.DataFrame] = None


def get_df() -> pd.DataFrame:
    global _df_cache
    if _df_cache is not None:
        return _df_cache
    if DATA_PATH.exists():
        _df_cache = pd.read_csv(DATA_PATH)
        return _df_cache
    # Demo data
    return _gerar_demo()


def _gerar_demo() -> pd.DataFrame:
    import numpy as np
    rng = np.random.default_rng(42)
    bairros = list(BAIRROS_MANAUS.keys())
    pesos = [BAIRROS_MANAUS[b]["eleitores_est"] for b in bairros]
    pesos = [p / sum(pesos) for p in pesos]
    n = 10000
    b_escolhidos = rng.choice(bairros, size=n, p=pesos)
    zonas = [BAIRROS_MANAUS[b]["zona_eleitoral"] for b in b_escolhidos]
    generos = rng.choice(["M", "F"], size=n, p=[0.46, 0.54])
    idades = rng.integers(18, 75, size=n)
    return pd.DataFrame({
        "nome": [f"Eleitor {i+1}" for i in range(n)],
        "bairro": b_escolhidos,
        "zona": zonas,
        "genero": generos,
        "idade": idades,
        "telefone": [f"92 9{rng.integers(1000,9999)}-{rng.integers(1000,9999)}" for _ in range(n)],
    })


# ── Frontend ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = BASE_DIR / "templates" / "index.html"
    return html_path.read_text(encoding="utf-8")


# ── Upload ─────────────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    global _df_cache
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(content), encoding="latin1")
        except Exception as e:
            raise HTTPException(400, f"Erro ao ler arquivo: {e}")

    DATA_PATH.parent.mkdir(exist_ok=True)
    df.to_csv(DATA_PATH, index=False)
    _df_cache = df
    return {"ok": True, "registros": len(df), "colunas": list(df.columns)}


# ── Endpoints de dados ─────────────────────────────────────────────────────────

@app.get("/api/resumo")
async def resumo():
    df = get_df()
    engine = ElectoralAnalytics(df)
    return engine.resumo_cadastro()


@app.get("/api/projecao/{cenario}")
async def projecao(cenario: str = "realista"):
    if cenario not in ["pessimista", "realista", "otimista"]:
        cenario = "realista"
    df = get_df()
    engine = ElectoralAnalytics(df)
    return engine.projecao_votos(cenario)


@app.get("/api/monte-carlo")
async def monte_carlo():
    df = get_df()
    engine = ElectoralAnalytics(df)
    return engine.monte_carlo(10000)


@app.get("/api/territorial")
async def territorial():
    df = get_df()
    engine = ElectoralAnalytics(df)
    return engine.analise_territorial()


@app.get("/api/zonas")
async def zonas():
    df = get_df()
    engine = ElectoralAnalytics(df)
    return engine.analise_gaps_zonas()


@app.get("/api/crescimento")
async def crescimento():
    df = get_df()
    engine = ElectoralAnalytics(df)
    return engine.projecao_crescimento()


@app.get("/api/score")
async def score():
    df = get_df()
    engine = ElectoralAnalytics(df)
    return engine.score_viabilidade()


@app.get("/api/recomendacoes")
async def recomendacoes():
    df = get_df()
    engine = ElectoralAnalytics(df)
    return engine.recomendacoes_estrategicas()


@app.get("/api/tse/historico")
async def tse_historico():
    return HISTORICO_ALEAM


@app.get("/api/tse/perfil-eleitorado")
async def tse_perfil():
    return PERFIL_ELEITORADO_AM


@app.get("/api/tse/projecao2026")
async def tse_proj():
    return PROJECAO_2026


@app.get("/api/todos-cenarios")
async def todos_cenarios():
    df = get_df()
    engine = ElectoralAnalytics(df)
    return {
        "pessimista": engine.projecao_votos("pessimista"),
        "realista": engine.projecao_votos("realista"),
        "otimista": engine.projecao_votos("otimista"),
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
