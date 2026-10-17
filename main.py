import sys
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlmodel import SQLModel, Field, Session, create_engine, select
from sqlalchemy import Column, JSON
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import uvicorn

DATABASE_URL = "postgresql://postgres.emzlsfkojsttxnghgjwx:potbar-tugfuz-7zobCe@aws-1-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require"
engine = create_engine(DATABASE_URL)

class WorkoutSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    routine_name: str
    duration_seconds: int = Field(default=0)
    exercises: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))

class RoutineTemplate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    exercises: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))

@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(title="App de Ginásio API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# === ROTAS DE TEMPLATES ===
@app.get("/templates/", response_model=List[RoutineTemplate])
async def listar_templates():
    with Session(engine) as session: return session.exec(select(RoutineTemplate)).all()

@app.post("/templates/", response_model=RoutineTemplate)
async def criar_template(template: RoutineTemplate):
    with Session(engine) as session:
        session.add(template); session.commit(); session.refresh(template)
        return template

@app.put("/templates/{template_id}", response_model=RoutineTemplate)
async def editar_template(template_id: int, template_atualizado: RoutineTemplate):
    with Session(engine) as session:
        template = session.get(RoutineTemplate, template_id)
        if not template: return {"error": "Não encontrado"}
        template.name = template_atualizado.name
        template.exercises = template_atualizado.exercises
        session.add(template); session.commit(); session.refresh(template)
        return template

@app.delete("/templates/{template_id}")
async def apagar_template(template_id: int):
    with Session(engine) as session:
        template = session.get(RoutineTemplate, template_id)
        if template: session.delete(template); session.commit(); return {"ok": True}
        return {"error": "Não encontrado"}

# === ROTAS DE HISTÓRICO (TREINOS) ===
@app.get("/treinos/", response_model=List[WorkoutSession])
async def listar_historico():
    with Session(engine) as session: return session.exec(select(WorkoutSession).order_by(WorkoutSession.date.desc())).all()

@app.post("/treinos/", response_model=WorkoutSession)
async def adicionar_treino(treino: WorkoutSession):
    with Session(engine) as session:
        session.add(treino); session.commit(); session.refresh(treino)
        return treino

@app.delete("/treinos/{treino_id}")
async def apagar_treino(treino_id: int):
    with Session(engine) as session:
        treino = session.get(WorkoutSession, treino_id)
        if treino: session.delete(treino); session.commit(); return {"ok": True}
        return {"error": "Não encontrado"}

@app.put("/treinos/{treino_id}", response_model=WorkoutSession)
async def editar_treino(treino_id: int, treino_atualizado: WorkoutSession):
    with Session(engine) as session:
        treino = session.get(WorkoutSession, treino_id)
        if not treino: return {"error": "Não encontrado"}
        treino.routine_name = treino_atualizado.routine_name
        treino.exercises = treino_atualizado.exercises
        treino.duration_seconds = treino_atualizado.duration_seconds
        session.add(treino); session.commit(); session.refresh(treino)
        return treino

@app.get("/historico/{exercise_name}")
async def ultimo_treino_exercicio(exercise_name: str):
    with Session(engine) as session:
        treinos = session.exec(select(WorkoutSession).order_by(WorkoutSession.date.desc())).all()
        
        last_sets = None
        last_date = None
        last_note = ""
        max_weight = 0.0
        max_1rm = 0.0
        
        for treino in treinos:
            for ex in treino.exercises:
                if ex.get("name", "").lower() == exercise_name.lower():
                    # Guarda a nota mais recente que não esteja vazia
                    if not last_note and ex.get("note"):
                        last_note = ex.get("note")
                        
                    sets = ex.get("sets", [])
                    if len(sets) > 0:
                        if last_sets is None:
                            last_sets = sets
                            last_date = treino.date
                        # Calcula recordes históricos ignorando séries de aquecimento ('W')
                        for s in sets:
                            if s.get("type", "N") != "W":
                                w = float(s.get("weight_kg", 0))
                                r = int(s.get("reps", 0))
                                if w > max_weight: max_weight = w
                                rm = w * (1 + r / 30.0)
                                if rm > max_1rm: max_1rm = rm
                                
        if last_sets is not None or last_note != "":
            return {
                "date": last_date,
                "sets": last_sets or [],
                "note": last_note,
                "max_weight": max_weight,
                "max_1rm": max_1rm
            }
    return None

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
