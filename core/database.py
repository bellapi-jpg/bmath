"""
Banco de dados relacional — modelos completos
Sistema de Inteligência Eleitoral AM 2026
"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime,
    ForeignKey, Text, Boolean, Date, JSON
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# Vercel e ambientes serverless têm filesystem read-only; usa /tmp nesses casos
_data_dir = BASE_DIR / "data"
if not _data_dir.exists() or not os.access(str(_data_dir), os.W_OK):
    import tempfile
    DB_PATH = Path(tempfile.gettempdir()) / "electoral.db"
else:
    DB_PATH = _data_dir / "electoral.db"

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False,
                       connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ══════════════════════════════════════════════════════════════════
# CAMADA 1 — REFERÊNCIAS GEOGRÁFICAS / TSE
# ══════════════════════════════════════════════════════════════════

class ZonaEleitoral(Base):
    __tablename__ = "zonas_eleitorais"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(4), unique=True, nullable=False)
    nome = Column(String(120))
    municipio = Column(String(80), default="Manaus")
    uf = Column(String(2), default="AM")
    total_eleitores = Column(Integer, default=0)
    abstencao_historica = Column(Float, default=0.28)
    regiao_cidade = Column(String(40))         # Norte, Sul, Leste, Oeste, Centro

    secoes = relationship("SecaoEleitoral", back_populates="zona")
    bairros = relationship("BairroRef", back_populates="zona")


class SecaoEleitoral(Base):
    """Granularidade máxima TSE — onde os votos são de fato contados"""
    __tablename__ = "secoes_eleitorais"
    id = Column(Integer, primary_key=True)
    zona_id = Column(Integer, ForeignKey("zonas_eleitorais.id"))
    numero_secao = Column(String(8))
    local_votacao = Column(String(200))
    bairro = Column(String(100))
    total_eleitores = Column(Integer, default=0)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    zona = relationship("ZonaEleitoral", back_populates="secoes")
    resultados = relationship("ResultadoSecao", back_populates="secao")
    eleitores = relationship("Eleitor", back_populates="secao")


class BairroRef(Base):
    __tablename__ = "bairros_ref"
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False)
    zona_id = Column(Integer, ForeignKey("zonas_eleitorais.id"))
    classe_social = Column(String(10))          # A/B, B/C, C, C/D, D/E
    densidade = Column(String(20))              # muito_alta, alta, media, baixa
    total_eleitores_estimado = Column(Integer, default=0)
    renda_media_sm = Column(Float, nullable=True)  # salários mínimos
    populacao_estimada = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    zona = relationship("ZonaEleitoral", back_populates="bairros")


# ══════════════════════════════════════════════════════════════════
# CAMADA 2 — HISTÓRICO ELEITORAL TSE
# ══════════════════════════════════════════════════════════════════

class CandidatoHistorico(Base):
    __tablename__ = "candidatos_historico"
    id = Column(Integer, primary_key=True)
    ano_eleicao = Column(Integer)
    nome = Column(String(200))
    numero = Column(String(6))
    partido = Column(String(20))
    cargo = Column(String(60))
    votos_totais = Column(Integer)
    situacao = Column(String(30))              # ELEITO, NÃO ELEITO, SUPLENTE
    campo_politico = Column(String(30))        # esquerda, centro, direita
    municipio = Column(String(80), default="Manaus")


class ResultadoSecao(Base):
    """Resultado de candidato específico por seção eleitoral — cruzamento principal"""
    __tablename__ = "resultados_secao"
    id = Column(Integer, primary_key=True)
    secao_id = Column(Integer, ForeignKey("secoes_eleitorais.id"))
    candidato_id = Column(Integer, ForeignKey("candidatos_historico.id"))
    ano_eleicao = Column(Integer)
    votos = Column(Integer, default=0)
    pct_secao = Column(Float, default=0.0)     # % dos votos daquela seção

    secao = relationship("SecaoEleitoral", back_populates="resultados")


class EleicaoAgregada(Base):
    """Resultado agregado por bairro/zona para análise rápida"""
    __tablename__ = "eleicoes_agregadas"
    id = Column(Integer, primary_key=True)
    ano = Column(Integer)
    cargo = Column(String(60))
    bairro = Column(String(100), nullable=True)
    zona_codigo = Column(String(4), nullable=True)
    total_votos_validos = Column(Integer)
    total_eleitores_aptos = Column(Integer)
    abstencao_real = Column(Float)
    votos_nulos = Column(Integer)
    votos_brancos = Column(Integer)
    quociente_eleitoral = Column(Integer, nullable=True)


# ══════════════════════════════════════════════════════════════════
# CAMADA 3 — BASE PRÓPRIA DO CANDIDATO
# ══════════════════════════════════════════════════════════════════

class Eleitor(Base):
    __tablename__ = "eleitores"
    id = Column(Integer, primary_key=True)
    nome = Column(String(200))
    bairro = Column(String(100))
    zona_codigo = Column(String(4), nullable=True)
    secao_id = Column(Integer, ForeignKey("secoes_eleitorais.id"), nullable=True)
    genero = Column(String(1))                 # M / F
    idade = Column(Integer, nullable=True)
    faixa_etaria = Column(String(20))          # calculado no ingestion
    telefone = Column(String(20), nullable=True)
    escolaridade = Column(String(40), nullable=True)
    profissao = Column(String(80), nullable=True)
    data_cadastro = Column(Date, nullable=True)
    origem_cadastro = Column(String(40))       # evento, indicacao, online, porta-a-porta
    classe_social_estimada = Column(String(10), nullable=True)  # inferida pelo bairro
    score_fidelidade = Column(Float, default=0.72)  # probabilidade de voto
    multiplicador_influencia = Column(Float, default=2.2)  # pessoas que pode influenciar
    ativo = Column(Boolean, default=True)

    secao = relationship("SecaoEleitoral", back_populates="eleitores")
    lote_id = Column(Integer, ForeignKey("lotes_importacao.id"), nullable=True)
    lote = relationship("LoteImportacao", back_populates="eleitores")


class LoteImportacao(Base):
    """Rastreia cada upload de planilha"""
    __tablename__ = "lotes_importacao"
    id = Column(Integer, primary_key=True)
    nome_arquivo = Column(String(200))
    data_upload = Column(DateTime, default=datetime.utcnow)
    total_registros = Column(Integer)
    registros_validos = Column(Integer)
    registros_duplicados = Column(Integer, default=0)
    colunas_detectadas = Column(JSON)
    origem = Column(String(80))                # evento_X, captacao_online, etc.

    eleitores = relationship("Eleitor", back_populates="lote")


# ══════════════════════════════════════════════════════════════════
# CAMADA 4 — CAMPANHA
# ══════════════════════════════════════════════════════════════════

class EventoCampanha(Base):
    __tablename__ = "eventos_campanha"
    id = Column(Integer, primary_key=True)
    nome = Column(String(200))
    tipo = Column(String(40))                  # comicio, visita, panfletagem, live, debate
    data_evento = Column(Date)
    bairro = Column(String(100))
    zona_codigo = Column(String(4), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    publico_estimado = Column(Integer, default=0)
    cadastros_gerados = Column(Integer, default=0)  # cadastros após evento
    custo_estimado = Column(Float, default=0.0)
    observacoes = Column(Text, nullable=True)

    # ROI calculado
    votos_estimados_gerados = Column(Float, nullable=True)
    roi_votos_por_real = Column(Float, nullable=True)


class Voluntario(Base):
    __tablename__ = "voluntarios"
    id = Column(Integer, primary_key=True)
    nome = Column(String(200))
    bairro = Column(String(100))
    zona_codigo = Column(String(4), nullable=True)
    telefone = Column(String(20), nullable=True)
    nivel_engajamento = Column(String(20))     # lider, ativo, apoiador
    rede_contatos_estimada = Column(Integer, default=50)  # qtd de pessoas que alcança
    multiplicador_real = Column(Float, default=2.5)
    data_adesao = Column(Date, nullable=True)
    ativo = Column(Boolean, default=True)


class RecursoCampanha(Base):
    __tablename__ = "recursos_campanha"
    id = Column(Integer, primary_key=True)
    mes_ano = Column(String(7))               # "2026-03"
    categoria = Column(String(60))            # midia_social, evento, material, pessoal
    valor = Column(Float)
    bairro_foco = Column(String(100), nullable=True)
    zona_foco = Column(String(4), nullable=True)
    retorno_cadastros = Column(Integer, nullable=True)
    retorno_votos_estimados = Column(Float, nullable=True)


# ══════════════════════════════════════════════════════════════════
# CAMADA 5 — REDES SOCIAIS
# ══════════════════════════════════════════════════════════════════

class MetricaRedeSocial(Base):
    __tablename__ = "metricas_redes"
    id = Column(Integer, primary_key=True)
    data = Column(Date)
    rede = Column(String(20))                  # instagram, facebook, tiktok, youtube, whatsapp
    seguidores = Column(Integer, default=0)
    alcance_organico = Column(Integer, default=0)
    alcance_pago = Column(Integer, default=0)
    impressoes = Column(Integer, default=0)
    engajamento_total = Column(Integer, default=0)  # likes + comments + shares
    taxa_engajamento = Column(Float, default=0.0)
    novos_seguidores = Column(Integer, default=0)
    link_clicks = Column(Integer, default=0)
    perfil_geografico = Column(JSON, nullable=True)  # {cidade: %, bairro: %}
    perfil_demografico = Column(JSON, nullable=True) # {faixa: %, genero: %}

    posts = relationship("PostRedeSocial", back_populates="metrica_dia")


class PostRedeSocial(Base):
    __tablename__ = "posts_redes"
    id = Column(Integer, primary_key=True)
    metrica_id = Column(Integer, ForeignKey("metricas_redes.id"), nullable=True)
    rede = Column(String(20))
    data_post = Column(DateTime)
    tipo = Column(String(20))                  # foto, video, reels, stories, ao_vivo
    tema = Column(String(60))                  # proposta, visita, pessoal, debate
    bairro_contexto = Column(String(100), nullable=True)
    alcance = Column(Integer, default=0)
    impressoes = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comentarios = Column(Integer, default=0)
    compartilhamentos = Column(Integer, default=0)
    salvamentos = Column(Integer, default=0)
    cliques_perfil = Column(Integer, default=0)
    conversao_cadastros = Column(Integer, default=0)  # cadastros rastreados ao post

    metrica_dia = relationship("MetricaRedeSocial", back_populates="posts")


class AlcanceGeografico(Base):
    """Distribuição geográfica do alcance nas redes por período"""
    __tablename__ = "alcance_geografico"
    id = Column(Integer, primary_key=True)
    periodo_inicio = Column(Date)
    periodo_fim = Column(Date)
    rede = Column(String(20))
    bairro = Column(String(100), nullable=True)
    zona_codigo = Column(String(4), nullable=True)
    cidade = Column(String(80), default="Manaus")
    uf = Column(String(2), default="AM")
    alcance_estimado = Column(Integer, default=0)
    pct_do_total = Column(Float, default=0.0)
    seguidores_nessa_area = Column(Integer, default=0)


# ══════════════════════════════════════════════════════════════════
# CAMADA 6 — ANALYTICS PERSISTIDOS
# ══════════════════════════════════════════════════════════════════

class SnapshotProjecao(Base):
    """Salva projeções ao longo do tempo para rastrear evolução"""
    __tablename__ = "snapshots_projecao"
    id = Column(Integer, primary_key=True)
    data_calculo = Column(DateTime, default=datetime.utcnow)
    total_cadastros = Column(Integer)
    votos_pessimista = Column(Float)
    votos_realista = Column(Float)
    votos_otimista = Column(Float)
    prob_eleicao_mc = Column(Float)
    score_viabilidade = Column(Float)
    pct_quociente = Column(Float)
    parametros = Column(JSON)


class ScoreBairro(Base):
    """Score calculado por bairro — atualizado a cada recálculo"""
    __tablename__ = "scores_bairro"
    id = Column(Integer, primary_key=True)
    data_calculo = Column(DateTime, default=datetime.utcnow)
    bairro = Column(String(100))
    cadastros = Column(Integer)
    penetracao_pct = Column(Float)
    votos_estimados = Column(Float)
    roi_potencial = Column(Float)
    prioridade = Column(String(10))
    alcance_social_estimado = Column(Integer, default=0)
    eventos_realizados = Column(Integer, default=0)
    score_composto = Column(Float, default=0.0)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
