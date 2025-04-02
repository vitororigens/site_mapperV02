from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
import os
import sys
import logging
from datetime import datetime
import csv
import pandas as pd

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
    formatar_planilha: Optional[bool] = True

class MapeamentoResponse(BaseModel):
    job_id: str
    status: str
    message: str

class ArquivoXLSX(BaseModel):
    nome: str
    data_criacao: str
    tamanho: int
    caminho: str

class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    job_id: Optional[str] = None

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
            request.output_dir,
            request.formatar_planilha
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

@app.get("/api/mapeamento/{job_id}/download")
async def download_mapeamento(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    job = jobs[job_id]
    if job["status"] != "concluido":
        raise HTTPException(status_code=400, detail="Mapeamento ainda não concluído")
    
    # Usa o diretório de saída do job
    output_dir = job.get("output_dir", "output")
    logger.info(f"Procurando arquivos Excel em: {output_dir}")
    
    # Verifica se o diretório existe
    if not os.path.exists(output_dir):
        raise HTTPException(status_code=404, detail="Diretório de saída não encontrado")
    
    # Procura pelo arquivo Excel mais recente no diretório de saída
    excel_files = [f for f in os.listdir(output_dir) if f.endswith('.xlsx')]
    if not excel_files:
        logger.error(f"Nenhum arquivo Excel encontrado em: {output_dir}")
        raise HTTPException(status_code=404, detail="Arquivo Excel não encontrado")
    
    # Pega o arquivo mais recente
    latest_file = max(excel_files, key=lambda x: os.path.getctime(os.path.join(output_dir, x)))
    file_path = os.path.join(output_dir, latest_file)
    logger.info(f"Arquivo encontrado: {file_path}")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    # Extrai a data e hora do nome do arquivo
    file_name = os.path.basename(file_path)
    file_date = file_name.split('_')[1]  # DD-MM-YY
    file_time = file_name.split('_')[2].split('.')[0]  # HH-MM
    
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"SEPD_{file_date}_{file_time}.xlsx"
    )

@app.get("/api/historico", response_model=List[ArquivoXLSX])
async def listar_arquivos_xlsx():
    try:
        output_dir = "output"  # Diretório padrão de saída
        if not os.path.exists(output_dir):
            raise HTTPException(status_code=404, detail="Diretório de saída não encontrado")
        
        arquivos = []
        for arquivo in os.listdir(output_dir):
            if arquivo.endswith('.xlsx'):
                caminho_completo = os.path.join(output_dir, arquivo)
                arquivos.append(ArquivoXLSX(
                    nome=arquivo,
                    data_criacao=datetime.fromtimestamp(os.path.getctime(caminho_completo)).strftime('%Y-%m-%d %H:%M:%S'),
                    tamanho=os.path.getsize(caminho_completo),
                    caminho=caminho_completo
                ))
        
        # Ordena os arquivos por data de criação (mais recentes primeiro)
        arquivos.sort(key=lambda x: x.data_criacao, reverse=True)
        return arquivos

    except Exception as e:
        logger.error(f"Erro ao listar arquivos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/historico/download/{nome_arquivo}")
async def download_arquivo_historico(nome_arquivo: str):
    try:
        output_dir = "output"
        caminho_arquivo = os.path.join(output_dir, nome_arquivo)
        
        if not os.path.exists(caminho_arquivo):
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        
        if not nome_arquivo.endswith('.xlsx'):
            raise HTTPException(status_code=400, detail="Arquivo não é um arquivo Excel válido")
        
        return FileResponse(
            caminho_arquivo,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=nome_arquivo
        )

    except Exception as e:
        logger.error(f"Erro ao baixar arquivo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs", response_model=List[LogEntry])
async def listar_logs():
    try:
        logs = []
        log_files = [
            "api.log",
            "formatter.log",
            "site_mapper.log"
        ]
        
        # Lista de codificações para tentar
        encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
        
        for log_file in log_files:
            if os.path.exists(log_file):
                # Tentar diferentes codificações
                for encoding in encodings:
                    try:
                        with open(log_file, 'r', encoding=encoding) as f:
                            for line in f:
                                try:
                                    # Parse do formato de log: "2024-04-01 22:35:00,000 - name - INFO - message"
                                    parts = line.strip().split(' - ')
                                    if len(parts) >= 4:
                                        timestamp = parts[0]
                                        name = parts[1]
                                        level = parts[2]
                                        message = ' - '.join(parts[3:])
                                        
                                        # Extrair job_id do nome do logger se disponível
                                        job_id = None
                                        if name.startswith('job_'):
                                            job_id = name.split('_')[1]
                                        
                                        logs.append(LogEntry(
                                            timestamp=timestamp,
                                            level=level,
                                            message=message,
                                            job_id=job_id
                                        ))
                                except Exception as e:
                                    logger.error(f"Erro ao processar linha de log: {str(e)}")
                                    continue
                        # Se chegou aqui, a codificação funcionou
                        break
                    except UnicodeDecodeError:
                        # Se falhou, tenta a próxima codificação
                        continue
                    except Exception as e:
                        logger.error(f"Erro ao ler arquivo {log_file}: {str(e)}")
                        break
        
        # Ordenar logs por timestamp (mais recentes primeiro)
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        return logs

    except Exception as e:
        logger.error(f"Erro ao listar logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs/download")
async def download_logs():
    try:
        # Criar um arquivo CSV temporário
        temp_csv = "temp_logs.csv"
        logs = await listar_logs()
        
        # Converter logs para DataFrame
        df = pd.DataFrame([log.dict() for log in logs])
        
        # Salvar como CSV
        df.to_csv(temp_csv, index=False)
        
        # Retornar o arquivo
        return FileResponse(
            temp_csv,
            media_type="text/csv",
            filename=f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
    except Exception as e:
        logger.error(f"Erro ao baixar logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def executar_mapeamento(job_id: str, url: str, site_prefix: str, 
                            concurrent_requests: int, rate_limit: int, output_dir: str,
                            formatar_planilha: bool = True):
    try:
        jobs[job_id]["status"] = "em_andamento"
        jobs[job_id]["message"] = "Mapeando site..."

        # Criar diretório de saída se não existir
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Diretório de saída criado/verificado: {output_dir}")

        # Executar mapeamento
        mapper = SiteMapper(
            start_url=url,
            req_per_second=rate_limit,
            concurrent_requests=concurrent_requests
        )
        
        # Mapear o site
        await mapper.map_site()
        logger.info(f"Site mapeado com sucesso. Arquivo CSV: {mapper.csv_file}")
        
        # Formatar resultados apenas se formatar_planilha for True
        if formatar_planilha:
            formatter = PlanilhaFormatter(
                input_csv=mapper.csv_file,
                output_dir=output_dir,
                site_prefix=site_prefix
            )
            formatter.process()
            logger.info(f"Planilha formatada e salva em: {output_dir}")

        jobs[job_id]["status"] = "concluido"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "Mapeamento concluído com sucesso"
        jobs[job_id]["output_dir"] = output_dir  # Adiciona o diretório de saída ao job

    except Exception as e:
        logger.error(f"Erro durante o mapeamento: {str(e)}")
        jobs[job_id]["status"] = "erro"
        jobs[job_id]["message"] = f"Erro durante o mapeamento: {str(e)}"

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
