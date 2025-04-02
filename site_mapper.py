import aiohttp
import asyncio
from bs4 import BeautifulSoup
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Set, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field
import re
import time
import random
from aiolimiter import AsyncLimiter
from services.page_node import PageTree
from models.page_data import PageData
from utils.url_utils import URLUtils
from utils.file_utils import FileUtils
import csv
import os
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

class SiteMapper:
    def __init__(self, start_url: str, test_mode: bool = False, 
                 req_per_second: int = 5, connection_timeout: int = 30,
                 max_retries: int = 3, concurrent_requests: int = 10):
        self.start_url = start_url
        self.domain = urlparse(start_url).netloc
        self.pages: Dict[str, PageData] = {}
        self.visited: Set[str] = set()
        self.news_urls: Set[str] = set()
        self.site_name: str = "Raiz" 
        self.page_tree = PageTree(root_name=self.site_name)
        
        # Configurações de controle
        self.test_mode = test_mode
        self.max_pages = 30 if test_mode else float('inf')
        self.req_per_second = req_per_second
        self.connection_timeout = connection_timeout
        self.max_retries = max_retries
        self.concurrent_requests = concurrent_requests
        
        # Rate limiter para controlar requisições por segundo
        self.rate_limiter = AsyncLimiter(req_per_second, 1)  
        
        # Semáforo para limitar conexões concorrentes
        self.semaphore = asyncio.Semaphore(concurrent_requests)
        
        # Configuração usando FileUtils
        self.csv_file = f"logs/pages_{FileUtils.generate_timestamp()}.csv"
        FileUtils.ensure_directory("logs")
        self._init_csv()
        
        # Inicializa URLUtils com o domínio
        self.url_utils = URLUtils(self.domain)
        
        logger.info(f"SiteMapper iniciado:")
        logger.info(f"- Modo de teste: {'ativado' if test_mode else 'desativado'}")
        logger.info(f"- Requisições por segundo: {req_per_second}")
        logger.info(f"- Timeout de conexão: {connection_timeout}s")
        logger.info(f"- Máximo de tentativas: {max_retries}")
        logger.info(f"- Requisições concorrentes: {concurrent_requests}")

    def _init_csv(self):
        """Inicializa arquivo CSV com o novo padrão de colunas."""
        headers = [
            # [Links]
            'De',
            'Para',
            # [Fase de mapeamento]
            'Tipo de migração',
            'Qtd de conteúdos',
            'Qtd de arquivos',
            'Verificar Cópias',
            # [Informações sobre a página]
            'Hierarquia',
            'Visibilidade',
            'Menu Lateral',
            'Breadcrumb',
            'Vocabulário',
            'Categoria',
            'Pontos de atenção',
            'Redes sociais',
            'Tipo de página',
            'Nome da página',
            'Link da página para a qual redireciona',
            'Complexidade',
            'Layout',
            'Data Descoberta'
        ]
        FileUtils.init_csv(self.csv_file, headers)

    def _save_to_csv(self, page: PageData):
        """Salva usando FileUtils"""
        row = page.to_planilha_row()
        FileUtils.append_to_csv(self.csv_file, row)

    def _should_continue_mapping(self) -> bool:
        """Verifica se ainda deve continuar o mapeamento (limite no modo de teste)"""
        if not self.test_mode:
            return True
        
        return len(self.pages) < self.max_pages

    async def _fetch_page(self, url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """
        Busca uma página com tratamento de erros e retry.
        Implementa controle de taxa e concorrência.
        """
        retry_count = 0
        
        while retry_count < self.max_retries:
            try:
                # Limita a taxa de requisições
                async with self.rate_limiter:
                    # Limita o número de conexões simultâneas
                    async with self.semaphore:
                        # Adiciona jitter para evitar rajadas
                        jitter = random.uniform(0, 0.5)
                        await asyncio.sleep(jitter)
                        
                        async with session.get(
                            url, 
                            timeout=aiohttp.ClientTimeout(total=self.connection_timeout),
                            ssl=False
                        ) as response:
                            if response.status == 200:
                                return await response.text()
                            elif response.status == 429:  # Too Many Requests
                                logger.warning(f"Rate limit atingido para {url}, esperando antes de tentar novamente")
                                await asyncio.sleep(5 + retry_count * 2)  # Backoff exponencial
                            else:
                                logger.warning(f"Status {response.status} para {url}")
                                return None
            except asyncio.TimeoutError:
                logger.warning(f"Timeout ao acessar {url}, tentativa {retry_count+1}/{self.max_retries}")
            except Exception as e:
                logger.warning(f"Erro ao acessar {url}: {str(e)}, tentativa {retry_count+1}/{self.max_retries}")
            
            retry_count += 1
            if retry_count < self.max_retries:
                # Backoff exponencial entre tentativas
                await asyncio.sleep(2 ** retry_count)
        
        logger.error(f"Falha após {self.max_retries} tentativas para {url}")
        return None

    async def _fetch_site_name(self):
        """Obtém o nome do site do title da página inicial."""
        try:
            async with aiohttp.ClientSession() as session:
                html = await self._fetch_page(self.start_url, session)
                if html:
                    soup = BeautifulSoup(html, 'html.parser')
                    title = soup.find('title')
                    if title:
                        # Remove extras comuns em títulos como " - GDF" ou similar
                        site_name = title.text.strip()
                        site_name = re.sub(r'\s*[-|]\s*.*$', '', site_name)
                        self.site_name = site_name
                        logger.info(f"Nome do site obtido: {self.site_name}")
                        
                        # Recria o PageTree com o novo nome raiz
                        self.page_tree = PageTree(root_name=self.site_name)
                        return True
                                
            logger.error("Não foi possível obter o nome do site do title")
        except Exception as e:
            logger.error(f"Erro ao obter nome do site: {e}")
        
        return False 

    def _normalize_url(self, url: str) -> str:
        """Normaliza URL removendo parâmetros e fragmentos."""
        parsed = urlparse(url)
        # Remove query parameters e fragments
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        # Remove trailing slash
        return normalized.rstrip('/')

    def _is_homepage(self, url: str) -> bool:
        """Verifica se a URL é a página inicial."""
        normalized_url = self._normalize_url(url)
        normalized_start = self._normalize_url(self.start_url)
        return normalized_url == normalized_start

    def _is_page_mapped(self, url: str) -> bool:
        """Verifica se uma página já foi mapeada, usando URL normalizada."""
        normalized_url = self._normalize_url(url)
        return any(self._normalize_url(mapped_url) == normalized_url for mapped_url in self.pages.keys())

    async def _process_internal_links(self, url: str, soup: BeautifulSoup, current_hierarchy: List[str]):
        """Processa links internos na página."""
        if not self._should_continue_mapping():
            logger.info(f"Pulando processamento de links internos para {url}")
            return
            
        # Melhorado: Procurar links em toda a página, não apenas em containers específicos
        # Primeiro, tenta encontrar containers específicos
        containers = soup.find_all(['div', 'section', 'article'], class_=['paginas-internas', 'content', 'main-content', 'container'])
        
        # Se não encontrar containers específicos, usa o body inteiro
        if not containers:
            containers = [soup.find('body')]
            
        for container in containers:
            if not container:
                continue
                
            # Processar links em paralelo
            tasks = []
            for link in container.find_all('a', href=True):
                if not self._should_continue_mapping():
                    logger.info("Limite de páginas atingido. Interrompendo processamento.")
                    break
                    
                href = link.get('href', '').strip()
                if not href:
                    continue
                    
                internal_url = urljoin(url, href)
                normalized_url = self._normalize_url(internal_url)
                
                # Verificação unificada de URLs já processadas
                if (self._is_homepage(internal_url) or 
                    self._is_page_mapped(internal_url) or
                    normalized_url in {self._normalize_url(u) for u in self.visited} or
                    not self._is_valid_url(internal_url) or 
                    self._is_internal_file(internal_url) or 
                    self._is_external_gov_link(internal_url)):
                    continue
                
                link_title = self._extract_title(link)
                if not link_title:
                    continue
                    
                # Adiciona à lista de visitados antes de processar
                self.visited.add(normalized_url)
                
                new_hierarchy = current_hierarchy + [link_title]
                logger.info(f"Link interno encontrado: {link_title} -> {internal_url}")
                
                # Criar uma tarefa para processar este link
                task = asyncio.create_task(
                    self._process_internal_link(internal_url, link_title, new_hierarchy)
                )
                tasks.append(task)
            
            # Aguarda todas as tarefas concluírem
            if tasks:
                await asyncio.gather(*tasks)
                
    async def _process_internal_link(self, url: str, title: str, hierarchy: List[str]):
        """Processa um único link interno de forma assíncrona."""
        try:
            async with aiohttp.ClientSession() as session:
                html = await self._fetch_page(url, session)
                if not html:
                    return
                
                soup = BeautifulSoup(html, 'html.parser')
                
                breadcrumb = self._extract_breadcrumb(soup)
                if breadcrumb and self.url_utils.is_news_breadcrumb(breadcrumb):
                    logger.info(f"Link interno ignorado por ser notícia: {url}")
                    return
                
                # Páginas internas são sempre ocultas
                page = PageData(url, hierarchy, is_visible=False)
                page.tipo_pagina = "Página de Widget"
                page.breadcrumb_hierarchy = breadcrumb if breadcrumb else hierarchy
                
                await self._analyze_page_content(url, soup, page)
                self.page_tree.add_content_page(url, page, page.breadcrumb_hierarchy)
                self.pages[url] = page
                
                # Processa links internos desta nova página
                await self._process_internal_links(url, soup, hierarchy)
                    
        except Exception as e:
            logger.error(f"Erro ao processar link interno {url}: {e}", exc_info=True)

    def _generate_ordenated_csv(self):
        """
        Gera o CSV com as páginas ordenadas de forma hierárquica.
        
        A ordenação prioriza:
        1. Profundidade da hierarquia 
        2. Posição dentro da hierarquia
        3. URL como critério de desempate
        """
        # Recria o CSV com as páginas ordenadas
        logger.info("Gerando CSV final...")
        self._init_csv()
        
        def get_sort_key(page_item):
            url, page = page_item
            
            hierarchy = page.breadcrumb_hierarchy or [self.site_name]
            
            return (
                len(hierarchy),                # Profundidade da hierarquia
                hierarchy,                     # Hierarquia completa para agrupamento
                url                            # URL como desempate
            )
        
        # Ordena as páginas antes de salvar
        all_pages = sorted(self.pages.items(), key=get_sort_key)
        
        for url, page in all_pages:
            self._save_to_csv(page)
        
        total_pages = len(self.pages)
        if self.test_mode and total_pages >= self.max_pages:
            logger.info(f"CSV gerado! Total de páginas: {total_pages} (limitado pelo modo de teste)")
        else:
            logger.info(f"CSV gerado! Total de páginas: {total_pages}")

    async def map_site(self):
        """Inicia o mapeamento do site."""
        logger.info("Iniciando mapeamento...")
        start_time = time.time()
        
        # Cria um novo limitador para este loop de evento
        rate_limiter = AsyncLimiter(self.req_per_second, 1)
        self.rate_limiter = rate_limiter
        
        await self._fetch_site_name()
        
        logger.info("Fase 1: Processando menu e suas páginas internas...")
        await self.parse_menu()
        
        # Cria um novo limitador para cada fase principal
        rate_limiter = AsyncLimiter(self.req_per_second, 1)
        self.rate_limiter = rate_limiter
        
        logger.info("Fase 2: Processando sitemap e suas páginas internas...")
        await self.parse_sitemap()
        
        logger.info("Fase 3: Atualizando hierarquias...")
        self.page_tree.update_hierarchies()
        
        # Chama o método de geração de CSV ordenado
        self._generate_ordenated_csv()
        
        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(elapsed_time, 60)
        
        logger.info(f"Mapeamento concluído em {int(minutes)}m {int(seconds)}s!")
        logger.info(f"Total de páginas mapeadas: {len(self.pages)}")
        
        # Estatísticas adicionais
        types_count = {}
        layout_count = {}
        for page in self.pages.values():
            page_type = page.tipo_pagina
            layout = page.layout
            types_count[page_type] = types_count.get(page_type, 0) + 1
            layout_count[layout] = layout_count.get(layout, 0) + 1
        
        logger.info("Estatísticas por tipo de página:")
        for page_type, count in types_count.items():
            logger.info(f"- {page_type}: {count} páginas")
            
        logger.info("Estatísticas por layout:")
        for layout, count in layout_count.items():
            logger.info(f"- {layout}: {count} páginas")

    async def _process_page(self, url: str, session: aiohttp.ClientSession):
        """Processa uma página e extrai seu breadcrumb."""
        if not self._should_continue_mapping():
            return
            
        try:
            if url in self.visited:
                return

            self.visited.add(url)
            logger.info(f"Processando página: {url}")

            html = await self._fetch_page(url, session)
            if not html:
                return
                
            soup = BeautifulSoup(html, 'html.parser')
            
            breadcrumb = self._extract_breadcrumb(soup)
            if breadcrumb:
                if self.url_utils.is_news_breadcrumb(breadcrumb):
                    logger.info(f"Página ignorada por ser notícia (breadcrumb): {url}")
                    return
                
                # Define visibilidade baseada na hierarquia
                is_root_page = len(breadcrumb) == 2  # ["Raiz", "NOME"]
                
                # Cria a página com visibilidade apropriada
                page = PageData(url, breadcrumb, is_visible=is_root_page)
                
                # Define tipo de página baseado na hierarquia
                if is_root_page:
                    page.tipo_pagina = "Página Definida"
                    logger.info(f"Página raiz encontrada via breadcrumb: {url} -> Definida como 'Página Definida' e Visível")
                else:
                    page.tipo_pagina = "Página de Widget"
                    logger.info(f"Subpágina encontrada via breadcrumb: {url} -> Definida como 'Página de Widget' e Oculta")
                
                page.breadcrumb_hierarchy = breadcrumb
                await self._analyze_page_content(url, soup, page)
                
                # Adiciona à árvore e ao dicionário
                self.page_tree.add_content_page(url, page, breadcrumb)
                self.pages[url] = page
                
                # Processa links internos apenas para páginas que não são raiz
                if not is_root_page:
                    await self._process_internal_links(url, soup, breadcrumb)

        except Exception as e:
            logger.error(f"Erro ao processar página {url}: {e}", exc_info=True)

    async def _analyze_page_content(self, url: str, soup: BeautifulSoup, page: PageData):
        """Analisa conteúdo da página."""
        page.qtd_arquivos = 0
        page.qtd_conteudos = 0
        page.arquivos_internos.clear()
        page.arquivos_externos.clear()
        page.pontos_atencao = "-"  # Inicializa com valor padrão

        # 1. Primeiro tenta extrair categoria da URL se contiver /category/
        category = self._extract_category(url)
        if category:
            page.categoria = category
            logger.info(f"Categoria extraída da URL para {url}: {category}")
        else:
            # 2. Tenta extrair do breadcrumb - se a página pai for uma página de categoria
            breadcrumb = self._extract_breadcrumb(soup)
            if breadcrumb and len(breadcrumb) > 1:
                parent_title = breadcrumb[-2]  # Pega o título da página pai
                parent_url = None
                
                # Procura o link para a página pai no breadcrumb
                breadcrumb_links = soup.find('div', class_='breadcrumbs').find_all('a') if soup.find('div', class_='breadcrumbs') else []
                for link in breadcrumb_links:
                    if link.get_text(strip=True) == parent_title:
                        parent_url = urljoin(url, link.get('href'))
                        break
                
                if parent_url:
                    # Verifica se a página pai é uma página de categoria
                    if 'carta-de-servicos' in parent_url.lower() or 'category' in parent_url.lower():
                        page.categoria = parent_title
                        logger.info(f"Categoria extraída do breadcrumb (página pai) para {url}: {parent_title}")
            
            # 3. Se ainda não tem categoria, tenta usar o título do menu lateral
            if page.categoria == "-":
                menu = soup.find(['nav', 'div', 'aside'], 
                               class_=['menu', 'menu-lateral', 'menu-lateral-flutuante', 
                                     'sidebar', 'left-menu'])
                if menu:
                    # Tentar diferentes seletores para o título do menu
                    menu_title = None
                    for selector in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', '.title', '.menu-title']:
                        if isinstance(selector, str) and selector.startswith('.'):
                            menu_title = menu.find(class_=selector[1:])
                        else:
                            menu_title = menu.find(selector)
                            
                        if menu_title:
                            break
                            
                    if menu_title:
                        page.categoria = menu_title.get_text(strip=True)
                        logger.info(f"Categoria extraída do menu lateral para {url}: {page.categoria}")
                    else:
                        page.categoria = "-"
                        logger.info("Menu lateral encontrado, mas sem título")

        # Melhorado: Buscar conteúdo em diferentes seletores, não apenas 'paginas-internas'
        main_content = soup.find(class_=['paginas-internas', 'conteudo', 'content', 'main-content'])
        if not main_content:
            main_content = soup.find(['main', 'article', 'div', 'section'])
        
        if not main_content:
            # Se não encontrar nenhum container de conteúdo, usa o body inteiro
            main_content = soup.find('body')
            
        if not main_content:
            logger.warning(f"Não foi possível encontrar conteúdo na página {url}")
            return
                
        # Procura por elementos colapsáveis (mais abrangente)
        colapsaveis = main_content.find_all(['div', 'section', 'article'], 
                                            class_=['collapse', 'accordion', 'panel-collapse', 
                                                    'panel-default', 'card', 'expandable'])
        if colapsaveis:
            page.pontos_atencao = "Página com Colapsável"
            logger.info(f"Página {url} possui elementos colapsáveis")
        
        # Elementos de conteúdo para contagem
        # Melhorado: Buscar diferentes tipos de containers
        conteudo_elements = []
        
        # 1. Conteúdo principal
        conteudo = main_content.find(id=['conteudo', 'content', 'main-content'])
        if conteudo:
            conteudo_elements.append(conteudo)
            
        # 2. Menu lateral
        menu = main_content.find(['nav', 'div', 'aside'], 
                                 class_=['menu', 'menu-lateral', 'menu-lateral-flutuante', 
                                         'sidebar', 'left-menu'])
        if menu:
            conteudo_elements.append(menu)
            page.layout = "30/70"
            logger.info(f"Página {url} possui menu - Layout definido como 30/70")
            
            # Tentar diferentes seletores para o título do menu
            menu_title = None
            for selector in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', '.title', '.menu-title']:
                if isinstance(selector, str) and selector.startswith('.'):
                    menu_title = menu.find(class_=selector[1:])
                else:
                    menu_title = menu.find(selector)
                    
                if menu_title:
                    break
                    
            if menu_title:
                page.menu_lateral = menu_title.get_text(strip=True)
                logger.info(f"Título do menu lateral encontrado: {page.menu_lateral}")
            else:
                page.menu_lateral = "-"
                logger.info("Menu lateral encontrado, mas sem título")
        else:
            page.layout = "1 Coluna"
            logger.info(f"Página {url} não possui menu - Layout definido como 1 Coluna")
        
        # 3. Corpo principal
        corpo_principal = main_content.find(class_=['corpo-principal', 'main-body', 'content-body'])
        if corpo_principal:
            conteudo_elements.append(corpo_principal)
            
        # 4. Contar também seções, artigos e divs importantes
        sections = main_content.find_all(['section', 'article'])
        content_divs = main_content.find_all('div', class_=['section', 'content-section', 'widget'])
        
        # Somamos os colapsáveis e outros elementos importantes de conteúdo
        page.qtd_conteudos = (
            len(colapsaveis) + 
            len(conteudo_elements) + 
            len(sections) + 
            len(content_divs)
        )
        
        # Limitar para que não seja um número absurdo (às vezes há muitas divs)
        if page.qtd_conteudos > 20:
            page.qtd_conteudos = 20
            
        # Detectar outros pontos de atenção
        tabs = main_content.find_all(['div', 'ul'], class_=['tabs', 'tab-content', 'nav-tabs'])
        if tabs and page.pontos_atencao == "-":
            page.pontos_atencao = "Página com Abas"
            
        forms = main_content.find_all('form')
        if forms and page.pontos_atencao == "-":
            page.pontos_atencao = "Página com Formulário"
            
        tables = main_content.find_all('table')
        if len(tables) > 2 and page.pontos_atencao == "-":
            page.pontos_atencao = "Página com Tabelas Complexas"

        # Processamento de arquivos
        await self._process_files(url, main_content, page)

    def _extract_breadcrumb(self, soup) -> Optional[List[str]]:
        """Extrai hierarquia do breadcrumb com suporte a mais formatos."""
        # Tentativa com o seletor original
        breadcrumb = soup.find('div', class_='breadcrumbs')
        
        # Se não encontrar, tenta outros seletores comuns
        if not breadcrumb:
            breadcrumb_selectors = [
                ('div', {'class': 'breadcrumb'}),
                ('ul', {'class': 'breadcrumb'}),
                ('nav', {'class': 'breadcrumb'}),
                ('div', {'id': 'breadcrumbs'}),
                ('ol', {'class': 'breadcrumb'}),
                ('nav', {'aria-label': 'Breadcrumb'})
            ]
            
            for selector, attrs in breadcrumb_selectors:
                breadcrumb = soup.find(selector, attrs)
                if breadcrumb:
                    break
        
        # Se ainda não encontrou, tenta uma abordagem mais genérica
        if not breadcrumb:
            for element in soup.find_all(['div', 'nav', 'ul', 'ol']):
                element_class = element.get('class', [])
                if element_class and any('bread' in cls.lower() for cls in element_class):
                    breadcrumb = element
                    break
        
        if not breadcrumb:
            return None

        # Usa o nome do site obtido como raiz
        hierarchy = [self.site_name]
        
        # Extrai links, independentemente da estrutura
        links = breadcrumb.find_all('a')
        
        # Pulamos o primeiro link (Home) se existir
        if links and any(home_text in links[0].text.strip().lower() for home_text in ['home', 'início', 'principal']):
            links = links[1:]
        
        # Adiciona os demais níveis
        for link in links:
            title = link.text.strip()
            if title and title.lower() not in ['home', 'início', 'principal', self.site_name.lower()]:
                hierarchy.append(title)
                
        # Tenta encontrar o item atual (que pode não ser um link)
        current = breadcrumb.find(['span', 'strong', 'li'], class_=['current', 'current-item', 'active'])
        if not current:
            # Se não encontrar, pega o último elemento que não seja um link
            last_items = breadcrumb.find_all(['span', 'strong', 'li'])
            if last_items:
                current = last_items[-1]
        
        if current and current.name != 'a':  # Certifica-se de que não é um link
            current_text = current.text.strip()
            if current_text and current_text.lower() not in ['home', 'início', 'principal', self.site_name.lower()]:
                # Verifica se já não está na lista
                if not hierarchy or hierarchy[-1] != current_text:
                    hierarchy.append(current_text)
                    
        return hierarchy if len(hierarchy) > 1 else None

    async def _process_files(self, url: str, container: BeautifulSoup, page: PageData):
        """Processa arquivos dentro do container."""
        # Melhorado: Procurar em toda a estrutura por links para arquivos
        for link in container.find_all('a', href=True):
            href = link.get('href', '').strip()
            if href:
                full_url = urljoin(url, href)
                if self._is_internal_file(full_url):
                    page.arquivos_internos.add(full_url)
                    page.qtd_arquivos += 1
                elif self._is_external_gov_link(full_url):
                    page.arquivos_externos.add(full_url)

    # Métodos de validação delegados para URLUtils
    def _is_valid_url(self, url: str) -> bool:
        return self.url_utils.is_valid_url(url)

    def _is_internal_file(self, url: str) -> bool:
        return self.url_utils.is_internal_file(url)

    def _is_external_gov_link(self, url: str) -> bool:
        return self.url_utils.is_external_gov_link(url)
    
    async def parse_menu(self):
        """Extrai links do menu principal com suporte a diferentes estruturas de menu."""
        logger.info(f"Iniciando parse do menu: {self.start_url} {'(modo de teste)' if self.test_mode else ''}")
        
        try:
            async with aiohttp.ClientSession() as session:
                html = await self._fetch_page(self.start_url, session)
                if not html:
                    logger.error("Não foi possível obter a página inicial")
                    return
                    
                soup = BeautifulSoup(html, 'html.parser')
                
                # Tentar diferentes seletores para o menu principal
                menu_selectors = [
                    ('ul', {'id': 'primary-menu'}),
                    ('nav', {'id': 'site-navigation'}),
                    ('ul', {'class': 'menu'}),
                    ('nav', {'class': 'main-navigation'}),
                    ('div', {'class': 'menu-principal-container'}),
                    ('div', {'class': 'navbar-collapse'}),
                    ('header', {'id': 'header'}),
                    ('div', {'class': 'header-menu'})
                ]
                
                menu = None
                for selector, attrs in menu_selectors:
                    menu = soup.find(selector, attrs)
                    if menu:
                        logger.info(f"Menu principal encontrado com seletor: {selector}, {attrs}")
                        break
                
                if not menu:
                    # Última tentativa - procurar pelo menu em qualquer nav do site
                    menu = soup.find('nav')
                    if menu:
                        logger.info("Menu principal encontrado via tag nav")
                    else:
                        logger.error("Menu principal não encontrado")
                        return
                
                logger.info("Processando menu principal...")
                
                # Procurar todos os links do menu, não apenas os itens de primeiro nível
                menu_items = self._extract_all_menu_items(menu)
                logger.info(f"Encontrados {len(menu_items)} itens de menu no total")
                
                # Processamento paralelo dos itens do menu
                tasks = []
                for item_info in menu_items:
                    if not self._should_continue_mapping():
                        logger.info("Limite de páginas atingido. Interrompendo processamento de menu.")
                        break
                    
                    url, title, hierarchy = item_info
                    if self._is_valid_url(url) and not self._is_page_mapped(url):
                        # Cria uma tarefa para cada item do menu
                        task = asyncio.create_task(
                            self._process_menu_item_directly(url, title, hierarchy)
                        )
                        tasks.append(task)
                
                # Aguarda todas as tarefas concluírem
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
        except Exception as e:
            logger.error(f"Erro ao processar menu: {e}", exc_info=True)

    def _extract_all_menu_items(self, menu_element):
        """
        Extrai todos os itens do menu, incluindo submenus, usando uma abordagem mais agressiva.
        
        Args:
            menu_element: Elemento do menu principal
            
        Returns:
            Lista de tuplas (url, título, hierarquia)
        """
        menu_items = []
        
        # Primeiro extrai todos os links diretamente
        for link in menu_element.find_all('a', href=True):
            url = link.get('href', '').strip()
            title = link.get_text(strip=True)
            
            if url and title and not self._is_external_gov_link(url) and not self._is_internal_file(url):
                # Primeiro, tentamos encontrar a hierarquia navegando para cima
                hierarchy = self._extract_menu_hierarchy(link)
                if not hierarchy or len(hierarchy) == 0:
                    hierarchy = ['Raiz', title]
                
                # Certifica-se de que a URL é absoluta
                full_url = urljoin(self.start_url, url)
                
                # Adiciona à lista
                menu_items.append((full_url, title, hierarchy))
        
        logger.info(f"Extraídos {len(menu_items)} links do menu")
        return menu_items
    
    def _extract_menu_hierarchy(self, link_element):
        """
        Determina a hierarquia de um item de menu percorrendo a árvore DOM para cima.
        
        Args:
            link_element: Elemento de link (a)
            
        Returns:
            Lista com a hierarquia do item ['Raiz', 'Nível 1', 'Nível 2', ...]
        """
        hierarchy = ['Raiz']
        
        # Primeiro adiciona o título do próprio link
        title = link_element.get_text(strip=True)
        if title:
            current_title = title
        else:
            return hierarchy  # Se não tem título, retorna só a raiz
        
        # Navega para cima buscando elementos de menu pai
        current = link_element.parent
        parent_titles = []
        
        # Subimos até 5 níveis buscando pais que sejam itens de menu ou títulos de seção
        depth = 0
        while current and depth < 5:
            # Procura por elementos que possam indicar um nível de menu
            if current.name in ['li', 'div'] and ('menu-item' in current.get('class', []) or 'dropdown' in current.get('class', [])):
                # Verifica se este item tem um link próprio ou um título
                parent_link = current.find('a', recursive=False)
                if parent_link and parent_link != link_element:
                    parent_title = parent_link.get_text(strip=True)
                    if parent_title and parent_title != title:
                        parent_titles.insert(0, parent_title)
                
            # Verifica se é um submenu (ul/div com classe submenu)
            elif current.name in ['ul', 'div'] and any(c in current.get('class', []) for c in ['sub-menu', 'dropdown-menu', 'submenu']):
                # Procura o item pai deste submenu
                prev_element = current.find_previous_sibling()
                if prev_element and prev_element.name == 'a':
                    parent_title = prev_element.get_text(strip=True)
                    if parent_title and parent_title != title:
                        parent_titles.insert(0, parent_title)
            
            current = current.parent
            depth += 1
        
        # Adiciona a hierarquia de pais encontrada
        hierarchy.extend(parent_titles)
        
        # Adiciona o título do próprio item
        hierarchy.append(current_title)
        
        return hierarchy

    async def _process_menu_item_directly(self, url, title, hierarchy):
        """
        Processa um item de menu diretamente com a hierarquia fornecida.
        
        Args:
            url: URL do item de menu
            title: Título do item
            hierarchy: Hierarquia do item
        """
        if not self._should_continue_mapping() or url in self.visited:
            return
            
        try:
            self.visited.add(url)
            logger.info(f"Processando item de menu: {title} -> {url}")

            # Define visibilidade baseada na profundidade da hierarquia
            is_root_page = len(hierarchy) <= 2  # ['Raiz', 'Menu Principal']
            
            # Cria a página com visibilidade apropriada
            page = PageData(url, hierarchy, is_visible=is_root_page)
            
            # Define tipo de página baseado na hierarquia
            if is_root_page:
                page.tipo_pagina = "Página Definida"
                logger.info(f"Página principal de menu: {title} -> Definida como 'Página Definida' e Visível")
            else:
                page.tipo_pagina = "Página de Widget"
                logger.info(f"Subitem de menu: {title} -> Definida como 'Página de Widget' e Oculta")
            
            # Salva a hierarquia no breadcrumb também
            page.breadcrumb_hierarchy = hierarchy.copy()
            
            # Carrega a página para analisar seu conteúdo
            async with aiohttp.ClientSession() as session:
                html = await self._fetch_page(url, session)
                if html:
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Verifica se há um breadcrumb na página que possa enriquecer a hierarquia
                    extracted_breadcrumb = self._extract_breadcrumb(soup)
                    if extracted_breadcrumb:
                        # Se encontrou um breadcrumb, ele tem prioridade
                        page.breadcrumb_hierarchy = extracted_breadcrumb
                        logger.info(f"Breadcrumb encontrado para {url}: {extracted_breadcrumb}")
                    
                    # Analisa o conteúdo da página
                    await self._analyze_page_content(url, soup, page)
                    
                    # Adiciona à árvore e ao dicionário
                    self.page_tree.add_content_page(url, page, page.breadcrumb_hierarchy)
                    self.pages[url] = page
                    
                    # Processa links internos apenas para páginas que não são de nível principal
                    if not is_root_page:
                        await self._process_internal_links(url, soup, hierarchy)
                    
        except Exception as e:
            logger.error(f"Erro ao processar item de menu {url}: {e}", exc_info=True)

    async def _process_menu_item(self, item, current_hierarchy):
        """Processa um item do menu e seus subitens."""
        if not self._should_continue_mapping():
            return
            
        try:
            link = item.find('a')
            if not link:
                return

            url = link.get('href', '').strip() if link.get('href') else ''
            title = link.get_text(strip=True)
            
            if not url or not title:
                return

            if self.url_utils.is_news_breadcrumb([title]):
                logger.info(f"Item de menu ignorado por ser notícia: {title} -> {url}")
                return

            new_hierarchy = current_hierarchy + [title]

            if self._is_valid_url(url):
                # Define visibilidade baseada na hierarquia
                is_root_page = len(new_hierarchy) == 2  # Página raiz (ex: ["Raiz", "INSTITUCIONAL"])
                
                page = PageData(url, new_hierarchy, is_visible=is_root_page)
                
                # Lógica para tipo de página e visibilidade
                if is_root_page:
                    page.tipo_pagina = "Página Definida"
                    logger.info(f"Página raiz encontrada: {title} -> Definida como 'Página Definida' e Visível")
                else:
                    page.tipo_pagina = "Página de Widget"
                    logger.info(f"Subpágina encontrada: {title} -> Definida como 'Página de Widget' e Oculta")

                self.page_tree.add_menu_page(new_hierarchy, url, page)
                self.pages[url] = page
                
                try:
                    async with aiohttp.ClientSession() as session:
                        html = await self._fetch_page(url, session)
                        if html:
                            soup = BeautifulSoup(html, 'html.parser')
                            await self._analyze_page_content(url, soup, page)
                            
                            # Processa links internos apenas para páginas que não são raiz
                            if not is_root_page:
                                await self._process_internal_links(url, soup, new_hierarchy)
                except Exception as e:
                    logger.error(f"Erro ao processar página do menu {url}: {e}")

            # Processa submenu se existir
            submenu = item.find('ul', class_='sub-menu')
            if submenu:
                # Processamento paralelo dos subitens do menu
                subtasks = []
                for subitem in submenu.find_all('li', class_='menu-item', recursive=False):
                    if not self._should_continue_mapping():
                        break
                        
                    # Cria uma tarefa para cada subitem do menu
                    subtask = asyncio.create_task(
                        self._process_menu_item(subitem, new_hierarchy)
                    )
                    subtasks.append(subtask)
                
                # Aguarda todas as subtarefas concluírem
                if subtasks:
                    await asyncio.gather(*subtasks, return_exceptions=True)
                            
        except Exception as e:
            logger.error(f"Erro ao processar item do menu: {str(e)}", exc_info=True)

    async def parse_sitemap(self):
        """Processa sitemap XML e extrai breadcrumbs."""
        logger.info(f"Iniciando parse do sitemap {'(modo de teste)' if self.test_mode else ''}")
        
        if not self._should_continue_mapping():
            logger.info("Limite de páginas atingido. Pulando processamento do sitemap.")
            return
            
        async with aiohttp.ClientSession() as session:
            sitemap_url = urljoin(self.start_url, 'sitemap.xml')
            
            try:
                html = await self._fetch_page(sitemap_url, session)
                if not html:
                    logger.error(f"Não foi possível acessar o sitemap em {sitemap_url}")
                    return
                    
                try:
                    root = ET.fromstring(html)
                    
                    sitemaps = root.findall('.//{*}loc')
                    logger.info(f"Encontrados {len(sitemaps)} sitemaps")
                    
                    # Processamento paralelo dos sitemaps
                    tasks = []
                    for sitemap in sitemaps:
                        if not self._should_continue_mapping():
                            logger.info("Limite de páginas atingido. Interrompendo processamento de sitemaps.")
                            break
                            
                        sitemap_url = sitemap.text
                        logger.info(f"Agendando processamento do sitemap: {sitemap_url}")
                        
                        task = asyncio.create_task(
                            self._process_sub_sitemap(sitemap_url, session)
                        )
                        tasks.append(task)
                    
                    # Aguarda todas as tarefas concluírem
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
                except ET.ParseError:
                    logger.error(f"Erro ao parsear o sitemap XML em {sitemap_url}")
                            
            except Exception as e:
                logger.error(f"Erro ao processar sitemap principal: {e}", exc_info=True)

    async def _process_sub_sitemap(self, sitemap_url: str, session: aiohttp.ClientSession):
        """Processa um sub-sitemap."""
        if not self._should_continue_mapping():
            return
            
        try:
            html = await self._fetch_page(sitemap_url, session)
            if not html:
                logger.error(f"Não foi possível acessar o sub-sitemap em {sitemap_url}")
                return
                
            try:
                root = ET.fromstring(html)
                
                urls = root.findall('.//{*}loc')
                logger.info(f"Processando {len(urls)} URLs em {sitemap_url}")
                
                # Processamento paralelo das URLs do sitemap
                tasks = []
                for url in urls:
                    if not self._should_continue_mapping():
                        logger.info("Limite de páginas atingido. Interrompendo processamento de URLs do sitemap.")
                        break
                        
                    page_url = url.text
                    if self._is_valid_url(page_url) and not self.url_utils.is_news_url(page_url):
                        task = asyncio.create_task(
                            self._process_page(page_url, session)
                        )
                        tasks.append(task)
                
                # Processa em lotes para evitar sobrecarga
                batch_size = min(self.concurrent_requests * 2, 20)  # Aumenta para aproveitar paralelismo
                for i in range(0, len(tasks), batch_size):
                    batch = tasks[i:i+batch_size]
                    if batch:
                        await asyncio.gather(*batch, return_exceptions=True)
                
            except ET.ParseError:
                logger.error(f"Erro ao parsear o XML do sub-sitemap em {sitemap_url}")
                
        except Exception as e:
            logger.error(f"Erro ao processar sub-sitemap {sitemap_url}: {e}", exc_info=True)

    def _hierarchies_match(self, menu_parts: List[str], breadcrumb_parts: List[str]) -> bool:
        """Verifica se hierarquias são equivalentes."""
        if not menu_parts or not breadcrumb_parts:
            return False

        def normalize(text):
            return text.lower().replace('-', ' ').replace('_', ' ').strip()

        menu_norm = [normalize(p) for p in menu_parts]
        bread_norm = [normalize(p) for p in breadcrumb_parts]

        return (
            menu_norm == bread_norm or
            (len(menu_norm) < len(bread_norm) and menu_norm == bread_norm[:len(menu_norm)]) or
            menu_norm[-1] == bread_norm[-1]
        )

    def _extract_title(self, link_element) -> Optional[str]:
        """Extrai o título de um link usando várias estratégias."""
        title = link_element.get_text(strip=True)
        if title:
            return title
            
        parent = link_element.parent
        if parent:
            if parent.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                title = parent.get_text(strip=True)
                if title:
                    return title
                    
            prev_heading = parent.find_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if prev_heading:
                title = prev_heading.get_text(strip=True)
                if title:
                    return title
                    
            next_heading = parent.find_next(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if next_heading:
                title = next_heading.get_text(strip=True)
                if title:
                    return title
        
        if link_element.get('title'):
            return link_element.get('title').strip()
        
        img = link_element.find('img')
        if img and img.get('alt'):
            return img.get('alt').strip()
            
        return None

    def _extract_category(self, url):
        """
        Extrai a categoria da URL apenas quando encontrar /category/.
        
        Args:
            url: URL a ser analisada
            
        Returns:
            str: Nome da categoria ou None se não for uma URL de categoria
        """
        try:
            parsed = urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            
            # Extrai apenas se tiver /category/ na URL
            if 'category' in path_parts:
                category_index = path_parts.index('category')
                if category_index + 1 < len(path_parts):
                    category = path_parts[category_index + 1]
                    # Capitalizar primeira letra e substituir hífens por espaços
                    category = category.replace('-', ' ').title()
                    return category
                    
        except Exception as e:
            logger.error(f"Erro ao extrair categoria da URL {url}: {str(e)}")
            
        return None

    def _write_to_csv(self, url, parent_url=None, category=None):
        """
        Registra uma página no arquivo CSV.
        """
        try:
            # Verifica se a página já existe no dicionário
            if url in self.pages:
                page = self.pages[url]
                if parent_url:
                    page.url_destino = parent_url
                if category:
                    page.categoria = category
            else:
                # Se não existir, cria um novo objeto PageData
                page = PageData(url=url, hierarchy=[self.site_name])
                page.url_destino = parent_url or ""
                page.categoria = category or "-"
            
            # Usar o método _save_to_csv que já está configurado corretamente
            self._save_to_csv(page)
        except Exception as e:
            logger.error(f"Erro ao escrever no CSV: {str(e)}")

    def save_to_csv(self):
        """
        Salva os dados mapeados em um arquivo CSV.
        """
        try:
            # Criar diretório de logs se não existir
            logs_dir = "logs"
            os.makedirs(logs_dir, exist_ok=True)
            
            # Gerar nome do arquivo com prefixo e data/hora
            now = datetime.now()
            file_prefix = "SEPD"
            file_date = now.strftime("%d-%m-%y")
            file_time = now.strftime("%H-%M")
            file_name = f"{file_prefix}_{file_date}_{file_time}"
            
            # Salvar CSV de páginas
            self.csv_file = f"{self.output_dir}/{file_name}.csv"
            self.df.to_csv(self.csv_file, index=False)
            logger.info(f"CSV salvo em: {self.csv_file}")
            
            # Salvar log do terminal
            log_file = f"{logs_dir}/{file_name}_log.csv"
            
            # Criar DataFrame com os logs
            log_data = {
                'timestamp': [],
                'level': [],
                'message': []
            }
            
            # Ler o arquivo de log atual
            with open('site_mapper.log', 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        parts = line.strip().split(' - ')
                        if len(parts) >= 4:
                            log_data['timestamp'].append(parts[0])
                            log_data['level'].append(parts[2])
                            log_data['message'].append(' - '.join(parts[3:]))
                    except Exception as e:
                        logger.error(f"Erro ao processar linha de log: {str(e)}")
                        continue
            
            # Criar e salvar o DataFrame de logs
            log_df = pd.DataFrame(log_data)
            log_df.to_csv(log_file, index=False)
            logger.info(f"Log do terminal salvo em: {log_file}")
            
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar CSV: {str(e)}")
            return False


# Script principal para executar o mapeador
async def run_mapper(url, test_mode=False, max_concurrent=10, rate_limit=5):
    """Função principal para executar o mapeador."""
    mapper = SiteMapper(
        url, 
        test_mode=test_mode, 
        concurrent_requests=max_concurrent,
        req_per_second=rate_limit
    )
    
    result = await mapper.map_site()
    return result

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Mapeador avançado de sites")
    parser.add_argument("url", help="URL inicial para mapeamento")
    parser.add_argument("--test", action="store_true", help="Executar em modo de teste (limite de 30 páginas)")
    parser.add_argument("--concurrent", type=int, default=10, help="Número máximo de requisições concorrentes")
    parser.add_argument("--rate", type=int, default=5, help="Requisições por segundo")
    
    args = parser.parse_args()
    
    asyncio.run(run_mapper(args.url, args.test, args.concurrent, args.rate))