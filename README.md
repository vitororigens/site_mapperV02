# Site Mapper

## Descrição

Este projeto é uma ferramenta para mapeamento de sites e formatação de resultados em planilhas Excel. Ele integra duas funcionalidades principais:

1. **SiteMapper** - Realiza o crawling e mapeamento do site.
2. **PlanilhaFormatter** - Formata os resultados para Excel com uma estrutura padronizada.

## Estrutura do Projeto

```
.
├── api/                    # API FastAPI
│   ├── main.py            # Endpoints da API
│   └── requirements.txt   # Dependências da API
├── frontend/              # Frontend React
│   ├── src/
│   │   ├── components/   # Componentes React
│   │   └── App.tsx       # Componente principal
│   └── package.json      # Dependências do frontend
├── models/               # Modelos de dados
├── services/            # Serviços de negócio
└── utils/              # Utilitários
```

## Requisitos

- Python 3.7 ou superior
- Node.js 16 ou superior
- Bibliotecas listadas em `api/requirements.txt`
- Dependências do frontend listadas em `frontend/package.json`

## Instalação

1. Clone o repositório:

    ```sh
    git clone https://github.com/seu-usuario/seu-repositorio.git
    cd seu-repositorio
    ```

2. Configure a API:

    ```sh
    cd api
    python -m venv venv
    source venv/bin/activate  # No Windows use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3. Configure o Frontend:

    ```sh
    cd frontend
    npm install
    ```

## Executando o Projeto

1. Inicie a API:

    ```sh
    cd api
    source venv/bin/activate  # No Windows use `venv\Scripts\activate`
    uvicorn main:app --reload
    ```

2. Em outro terminal, inicie o Frontend:

    ```sh
    cd frontend
    npm start
    ```

3. Acesse a aplicação em `http://localhost:3000`

## Funcionalidades

### Interface Web

- Formulário para configurar o mapeamento:
  - URL do site
  - Prefixo do site
  - Número de requisições concorrentes
  - Taxa de requisições por segundo
- Monitoramento em tempo real do progresso
- Exibição de status e mensagens de erro
- Download automático dos resultados

### API Endpoints

- `POST /api/mapeamento`: Inicia um novo mapeamento
- `GET /api/mapeamento/{job_id}`: Consulta o status de um mapeamento

## Exemplo de Uso

1. Acesse a interface web em `http://localhost:3000`
2. Preencha o formulário com:
   - URL do site a ser mapeado
   - Nome do site para substituir "Raiz"
   - Configurações de requisições (opcional)
3. Clique em "Iniciar Mapeamento"
4. Acompanhe o progresso em tempo real
5. Os resultados serão salvos automaticamente no diretório de saída

## Logs

Os logs da API são gerados no arquivo `api.log` e no console. Certifique-se de verificar os logs para detalhes sobre a execução e possíveis erros.
