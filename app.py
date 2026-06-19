"""
API Backend — Sistema de Inteligência Eleitoral AM 2026
FastAPI + SQLAlchemy + Motor Analítico Multicamada
"""
import io
import sys
import json
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import uvicorn

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from core.database import init_db, get_db, SessionLocal
from core.seed_tse import seed
from ingestion.pipeline import CadastroIngestion, SocialIngestion, EventoIngestion
from analytics.engine import (
    CadastroAnalytics, ProjecaoAnalytics, TerritorialAnalytics,
    SocialAnalytics, HistoricoAnalytics, CampanhaAnalytics,
    AlertasAnalytics, ScoreViabilidade
)

app = FastAPI(title="BMATH Electoral Intelligence", version="2.0")

if (BASE_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def startup():
    init_db()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


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
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(content), encoding="latin1")
        except Exception as e:
            raise HTTPException(400, f"Erro ao ler CSV: {e}")

    ingestor = CadastroIngestion(db)
    result = ingestor.ingest(df, file.filename, origem)
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


@app.get("/api/recomendacoes")
def recomendacoes(db: Session = Depends(get_db)):
    return ScoreViabilidade(db).recomendacoes()


# ── Demo seed (dados de demonstração) ─────────────────────────────────────────

@app.post("/api/demo/seed-cadastros")
def demo_seed(db: Session = Depends(get_db)):
    """Injeta 10.000 cadastros demo para demonstração"""
    import numpy as np
    from core.database import BairroRef, Eleitor, LoteImportacao
    from datetime import date, timedelta

    if db.query(Eleitor).count() > 0:
        return {"ok": True, "mensagem": "Cadastros já existem"}

    bairros = db.query(BairroRef).all()
    if not bairros:
        return {"ok": False, "mensagem": "Rode seed TSE primeiro"}

    rng = np.random.default_rng(42)
    pesos = [b.total_eleitores_estimado for b in bairros]
    soma = sum(pesos)
    pesos_norm = [p/soma for p in pesos]

    lote = LoteImportacao(
        nome_arquivo="demo_10000.csv", total_registros=10000,
        registros_validos=10000, colunas_detectadas={}, origem="demo"
    )
    db.add(lote)
    db.flush()

    generos = rng.choice(["M","F"], size=10000, p=[0.46,0.54])
    idades = rng.integers(18, 76, size=10000)
    escolhas = rng.choice(len(bairros), size=10000, p=pesos_norm)

    faixa_map = {(0,17):"≤17",(18,24):"18-24",(25,34):"25-34",(35,44):"35-44",(45,59):"45-59",(60,69):"60-69",(70,120):"70+"}
    score_map = {"≤17":0.58,"18-24":0.61,"25-34":0.72,"35-44":0.72,"45-59":0.78,"60-69":0.83,"70+":0.83}
    mult_map = {"muito_alta":2.8,"alta":2.2,"media":1.9,"baixa":1.6}
    orig = rng.choice(["evento","indicacao","online","porta-a-porta"], size=10000, p=[0.3,0.35,0.2,0.15])

    inicio = date(2024, 1, 1)
    datas = [inicio + timedelta(days=int(rng.integers(0, 540))) for _ in range(10000)]

    for i in range(10000):
        b = bairros[escolhas[i]]
        idade = int(idades[i])
        faixa = next((lbl for (lo,hi),lbl in faixa_map.items() if lo<=idade<=hi), "")
        dens = b.densidade or "media"
        el = Eleitor(
            nome=f"Eleitor Demo {i+1}", bairro=b.nome,
            zona_codigo=b.zona.codigo if b.zona else None,
            genero=generos[i], idade=idade, faixa_etaria=faixa,
            classe_social_estimada=b.classe_social,
            score_fidelidade=score_map.get(faixa, 0.70),
            multiplicador_influencia=mult_map.get(dens, 2.0),
            origem_cadastro=orig[i], data_cadastro=datas[i],
            lote_id=lote.id,
        )
        db.add(el)

    db.commit()
    return {"ok": True, "cadastros_criados": 10000}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
