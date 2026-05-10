# Oficina-Gest — Sistema de Gestão para Oficinas Mecânicas

Sistema ERP completo desenvolvido em Django para gerenciamento de oficinas mecânicas. Cobre todo o ciclo operacional: clientes, veículos, orçamentos, ordens de serviço, estoque, financeiro e relatórios.

---

## Funcionalidades

### Clientes
- Cadastro de pessoas físicas e jurídicas (CPF/CNPJ)
- Endereço com preenchimento automático via ViaCEP
- Histórico de veículos, OS e orçamentos na ficha do cliente
- Soft delete (desativação com preservação do histórico)
- Validação de CPF e CNPJ com dígito verificador

### Veículos
- Cadastro por marca, modelo, ano, combustível e placa
- Histórico completo de OS e orçamentos por veículo
- Alertas de revisão por data e quilometragem

### Orçamentos
- Fluxo completo: Rascunho → Enviado → Aprovado → OS Gerada
- Itens de serviço e peças com cálculo automático de totais
- Geração de OS a partir do orçamento aprovado
- Exportação para PDF (ReportLab)
- Validade configurável com alerta no dashboard

### Ordens de Serviço
- Ciclo de vida: Aberta → Em Andamento → Aguardando → Concluída → Entregue
- Adição rápida de serviços e peças direto da tela de detalhe
- Registro de KM de entrada e saída
- Registro de pagamento com integração ao módulo financeiro
- Exportação para PDF
- Alerta visual de OS atrasadas na listagem

### Estoque
- Controle de produtos com estoque mínimo e máximo
- Movimentações de entrada e saída com histórico
- Alertas de estoque abaixo do mínimo no dashboard
- Gestão de fornecedores com CNPJ
- Suporte a múltiplas unidades de medida

### Financeiro
- Lançamentos de receitas e despesas com categorias
- Três datas: competência, vencimento e pagamento
- Fluxo de caixa mensal
- Status: Pendente, Pago, Vencido, Cancelado
- Integração automática com pagamento de OS
- Sugestão automática de tipo (receita/despesa) por categoria

### Relatórios / Dashboard
- KPIs clicáveis: clientes ativos, OS em aberto, orçamentos pendentes, faturamento do mês
- Painel de orçamentos a vencer nos próximos 7 dias
- Gráfico de faturamento dos últimos 6 meses (Chart.js)
- Relatório de faturamento mensal com filtros
- Relatório de orçamentos por período
- Relatório de serviços mais realizados e clientes frequentes

### Controle de Acesso
- Três perfis de usuário: **Administrador**, **Mecânico** e **Recepcionista**
- Permissões por perfil em todas as views sensíveis
- Gestão de usuários exclusiva para Administradores

---

## Stack tecnológico

| Componente | Tecnologia |
|---|---|
| Backend | Django 4.2.11 |
| Frontend | Bootstrap 5.3 + Bootstrap Icons |
| Formulários | django-crispy-forms 2.1 + crispy-bootstrap5 |
| PDF | ReportLab 4.1 |
| Upload de imagens | Pillow 10.2 |
| Configuração | python-decouple 3.8 |
| Banco de dados | SQLite (dev) |
| Selects dinâmicos | Select2 4.1 |
| Máscaras de input | IMask.js 7.6 |
| Gráficos | Chart.js 4.4 |
| CEP automático | ViaCEP (API pública) |

---

## Pré-requisitos

- Python 3.10 ou superior
- pip
- Git (opcional)

---

## Instalação (desenvolvimento)

```bash
# 1. Clone ou extraia o projeto
git clone <url-do-repositorio>
cd "OFICINA-GEST"

# 2. Crie e ative o ambiente virtual
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Aplique as migrações
python manage.py migrate

# 5. Crie o superusuário administrador
python manage.py createsuperuser

# 6. (Opcional) Carregue dados de exemplo
python manage.py loaddata clientes/fixtures/clientes.json

# 7. Inicie o servidor de desenvolvimento
python manage.py runserver
```

Acesse: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## Estrutura do projeto

```
OFICINA-GEST/
├── accounts/          # Autenticação e perfis de usuário
├── clientes/          # Gestão de clientes PF e PJ
├── veiculos/          # Cadastro e histórico de veículos
├── orcamentos/        # Orçamentos com itens de serviço e peças
├── ordens_servico/    # OS com ciclo completo de status
├── estoque/           # Controle de produtos e movimentações
├── financeiro/        # Lançamentos e fluxo de caixa
├── relatorios/        # Dashboard e relatórios gerenciais
├── core/              # Mixins de permissão e template tags
├── templates/         # Templates HTML organizados por app
├── static/            # Arquivos estáticos (CSS, JS, imagens)
├── media/             # Uploads (avatares)
├── oficina/           # Configurações Django (settings, urls, wsgi)
├── manage.py
└── requirements.txt
```

---

## Preparação para produção

Antes de fazer deploy em produção, é **obrigatório** realizar os seguintes ajustes:

### 1. Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```ini
SECRET_KEY=gere-uma-chave-segura-aleatoria-aqui
DEBUG=False
ALLOWED_HOSTS=seudominio.com.br,www.seudominio.com.br
```

Atualize `settings.py` para usar `python-decouple`:

```python
from decouple import config

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')
```

### 2. Instalar dependências de produção

```bash
pip install gunicorn whitenoise
```

Adicione ao `requirements.txt`:
```
gunicorn
whitenoise
```

### 3. Coletar arquivos estáticos

```bash
python manage.py collectstatic --noinput
```

### 4. Nunca commitar o `.env`

Adicione ao `.gitignore`:
```
.env
db.sqlite3
media/
staticfiles/
```

---

## Opções de deploy recomendadas

| Plataforma | Indicado para | Dificuldade | Custo |
|---|---|---|---|
| **Railway.app** | Primeiro deploy, testes com cliente | Baixa | ~$5/mês |
| **VPS (Hetzner / Contabo)** | Produção definitiva, controle total | Média | $4-15/mês |
| **KingHost / Locaweb** | Hospedagem nacional, dados no Brasil | Média | R$50-80/mês |
| **PythonAnywhere** | Testes, hobby | Baixa | Grátis / $5/mês |

Para produção definitiva em uma oficina, recomenda-se **VPS + Nginx + Gunicorn** com banco PostgreSQL.

---

## Perfis de usuário

| Perfil | Acesso |
|---|---|
| **Administrador** | Acesso total: usuários, relatórios, financeiro, exclusões |
| **Recepcionista** | Clientes, veículos, OS, orçamentos, estoque, financeiro (lançamentos) |
| **Mecânico** | Visualização de OS atribuídas, atualização de status |

---

## Desenvolvido por

**Leandro Lopes**  
Sistema de gestão desenvolvido para oficinas mecânicas de pequeno e médio porte.

---

## Licença

Uso privado — todos os direitos reservados.
# OFICINA-GEST
