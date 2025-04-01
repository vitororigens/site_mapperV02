from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
import os
import sys
import logging
from datetime import datetime

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from site_mapper import SiteMapper
from planilha_formatter import PlanilhaFormatter

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Site Mapper API")

# Configuração do CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique as origens permitidas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MapeamentoRequest(BaseModel):
    url: str
    site_prefix: Optional[str] = None
    concurrent_requests: Optional[int] = 10
    rate_limit: Optional[int] = 5
    output_dir: Optional[str] = "output"

class MapeamentoResponse(BaseModel):
    job_id: str
    status: str
    message: str

# Armazenamento temporário de jobs (em produção, use um banco de dados)
jobs = {}

@app.post("/api/mapeamento", response_model=MapeamentoResponse)
async def iniciar_mapeamento(request: MapeamentoRequest, background_tasks: BackgroundTasks):
    try:
        job_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        jobs[job_id] = {
            "status": "iniciando",
            "progress": 0,
            "message": "Iniciando mapeamento..."
        }

        background_tasks.add_task(
            executar_mapeamento,
            job_id,
            request.url,
            request.site_prefix,
            request.concurrent_requests,
            request.rate_limit,
            request.output_dir
        )

        return MapeamentoResponse(
            job_id=job_id,
            status="iniciando",
            message="Mapeamento iniciado com sucesso"
        )

    except Exception as e:
        logger.error(f"Erro ao iniciar mapeamento: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mapeamento/{job_id}")
async def status_mapeamento(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return jobs[job_id]

async def executar_mapeamento(job_id: str, url: str, site_prefix: str, 
                            concurrent_requests: int, rate_limit: int, output_dir: str):
    try:
        jobs[job_id]["status"] = "em_andamento"
        jobs[job_id]["message"] = "Mapeando site..."

        # Criar diretório de saída se não existir
        os.makedirs(output_dir, exist_ok=True)

        # Executar mapeamento
        mapper = SiteMapper(
            start_url=url,
            req_per_second=rate_limit,
            concurrent_requests=concurrent_requests
        )
        
        # Mapear o site
        await mapper.map_site()
        
        # Formatar resultados
        formatter = PlanilhaFormatter(
            input_csv=mapper.csv_file,
            output_dir=output_dir,
            site_prefix=site_prefix
        )
        formatter.format()

        jobs[job_id]["status"] = "concluido"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "Mapeamento concluído com sucesso"

    except Exception as e:
        logger.error(f"Erro durante o mapeamento: {str(e)}")
        jobs[job_id]["status"] = "erro"
        jobs[job_id]["message"] = f"Erro durante o mapeamento: {str(e)}"

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
