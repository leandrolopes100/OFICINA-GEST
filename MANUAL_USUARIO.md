# Manual do Usuário — Oficina-Gest

**Sistema de Gestão para Oficinas Mecânicas**  
Versão 1.0

---

## Sumário

1. [Introdução](#1-introdução)
2. [Acesso ao Sistema](#2-acesso-ao-sistema)
3. [Dashboard — Painel Principal](#3-dashboard--painel-principal)
4. [Clientes](#4-clientes)
5. [Veículos](#5-veículos)
6. [Orçamentos](#6-orçamentos)
7. [Ordens de Serviço (OS)](#7-ordens-de-serviço-os)
8. [Estoque](#8-estoque)
9. [Financeiro](#9-financeiro)
10. [Relatórios](#10-relatórios)
11. [Meu Perfil](#11-meu-perfil)
12. [Fluxos Completos — Passo a Passo](#12-fluxos-completos--passo-a-passo)
13. [Permissões por Perfil](#13-permissões-por-perfil)
14. [Dicas e Boas Práticas](#14-dicas-e-boas-práticas)

---

## 1. Introdução

O **Oficina-Gest** é um sistema de gestão desenvolvido especialmente para oficinas mecânicas. Com ele você consegue:

- Cadastrar e acompanhar clientes e seus veículos
- Criar orçamentos detalhados com serviços e peças
- Abrir e controlar Ordens de Serviço (OS) do início à entrega
- Controlar o estoque de peças e materiais
- Registrar receitas e despesas do caixa
- Visualizar relatórios e indicadores do negócio

Todas as informações ficam centralizadas e conectadas — ao abrir uma OS, o sistema já conhece o cliente, o veículo, o histórico e o orçamento aprovado.

---

## 2. Acesso ao Sistema

### Login

1. Abra o navegador e acesse o endereço fornecido pelo administrador
2. Na tela de login, informe seu **usuário** e **senha**
3. Clique em **Entrar**

> Se esqueceu sua senha, solicite ao administrador que a redefina pelo painel de usuários.

### Navegação

Após o login, a **barra lateral esquerda** dá acesso a todos os módulos do sistema. Ela fica sempre visível.

---

## 3. Dashboard — Painel Principal

O Dashboard é a primeira tela após o login. Ele mostra um resumo do estado atual da oficina.

### Cartões de indicadores (KPIs)

| Cartão | O que significa |
|---|---|
| **Clientes Ativos** | Total de clientes cadastrados e ativos. Clique para ver a lista. |
| **OS em Aberto** | OS abertas, em andamento ou aguardando. Clique para ver a lista filtrada. |
| **Orçamentos Pendentes** | Orçamentos em rascunho ou enviados, aguardando aprovação. |
| **Faturamento do Mês** | Total de receitas pagas no mês atual. Clique para ver o relatório. |

### Painel de orçamentos a vencer

Se houver orçamentos com validade nos próximos **7 dias**, um painel de alerta aparece abaixo dos KPIs. As linhas ficam vermelhas (0–2 dias) ou amarelas (3–5 dias). Clique em **Ver** para acessar o orçamento diretamente.

### Gráfico de faturamento

Exibe as receitas e despesas dos últimos 6 meses para uma visão rápida da saúde financeira.

### OS Recentes e Orçamentos Recentes

As últimas movimentações aparecem no rodapé do dashboard para acesso rápido.

---

## 4. Clientes

### O que é

O cadastro de clientes armazena as informações de cada pessoa (física ou jurídica) que utiliza os serviços da oficina.

### Como cadastrar um novo cliente

1. No menu lateral, clique em **Clientes**
2. Clique no botão **Novo Cliente** (canto superior direito)
3. Preencha os campos:
   - **Tipo**: Pessoa Física (CPF) ou Pessoa Jurídica (CNPJ)
   - **Nome / Razão Social**: nome completo ou da empresa
   - **CPF / CNPJ**: o sistema valida automaticamente
   - **Telefone** e **Celular**: com DDD
   - **E-mail**: opcional
   - **CEP**: ao sair do campo, o endereço é preenchido automaticamente
4. Clique em **Salvar Cliente**

> **Dica:** Ao selecionar a categoria **Pessoa Física** ou **Jurídica**, o campo CPF/CNPJ muda a máscara automaticamente.

### Como buscar um cliente

Na tela de lista de clientes, use a barra de busca para localizar por **nome**, **CPF/CNPJ** ou **telefone**.

### Ficha do cliente

Ao clicar no nome do cliente, você acessa a ficha completa com:
- Dados cadastrais
- Veículos vinculados
- Últimas Ordens de Serviço
- Últimos Orçamentos

A partir desta tela você pode **Editar**, **Novo Veículo**, **Desativar** ou **Reativar** o cliente.

### Clientes inativos

Clientes desativados não somem do sistema — são preservados no histórico. Para visualizá-los, clique no botão **Inativos (N)** no canto superior da lista. Para reativar, clique no botão **Reativar** na linha do cliente.

---

## 5. Veículos

### O que é

Cada cliente pode ter um ou mais veículos cadastrados. O histórico de OS e orçamentos fica vinculado ao veículo.

### Como cadastrar um veículo

**Opção 1:** Na ficha do cliente, clique em **Novo Veículo**. O cliente já vem pré-selecionado.

**Opção 2:** No menu lateral, clique em **Veículos** → **Novo Veículo**.

Campos principais:
- **Cliente**: a quem o veículo pertence
- **Marca / Modelo / Ano**
- **Placa** (campo transforma automaticamente em maiúsculas)
- **Combustível**
- **KM Atual**

### Ficha do veículo

Exibe todos os dados do veículo, o histórico de OS e o histórico de orçamentos. A partir desta tela você pode:
- **Novo Orçamento** → abre o formulário já com cliente e veículo preenchidos
- **Nova OS** → abre o formulário já com cliente e veículo preenchidos

---

## 6. Orçamentos

### O que é

O orçamento é o documento enviado ao cliente antes de iniciar o serviço, detalhando o que será feito e o custo. Após aprovado pelo cliente, ele pode ser convertido em OS.

### Ciclo de vida de um orçamento

```
Rascunho → Enviado ao Cliente → Aprovado → OS Gerada
               ↓
            Reprovado
```

### Como criar um orçamento

1. No menu lateral, clique em **Orçamentos** → **Novo Orçamento**
2. Preencha os dados gerais:
   - **Cliente**: selecione o cliente
   - **Veículo**: após selecionar o cliente, o campo carrega automaticamente os veículos daquele cliente
   - **Válido até**: data de validade do orçamento
3. Na seção **Serviços / Mão de Obra**, clique em **+ Adicionar** para incluir serviços:
   - Selecione o tipo de serviço (o preço e descrição são preenchidos automaticamente)
   - Ajuste a quantidade e o preço se necessário
4. Na seção **Peças / Materiais**, clique em **+ Adicionar** para incluir peças
5. O **resumo financeiro** é atualizado em tempo real enquanto você digita
6. Clique em **Salvar Orçamento**

### Ações disponíveis no detalhe do orçamento

Após salvo, na tela de detalhe:

| Ação | Quando aparece | O que faz |
|---|---|---|
| **Enviar ao Cliente** | Status: Rascunho | Marca como enviado ao cliente |
| **Aprovar** | Status: Enviado | Marca como aprovado |
| **Mais ações → Editar** | Status: Rascunho ou Enviado | Volta para edição |
| **Mais ações → Aprovar diretamente** | Status: Rascunho | Aprova sem precisar enviar |
| **Mais ações → Reprovar** | Status: Enviado | Marca como reprovado |
| **Gerar OS** | Status: Aprovado | Cria uma OS com todos os itens do orçamento |
| **Baixar PDF** | Sempre | Gera o PDF do orçamento |

> **Atenção:** Após aprovado ou reprovado, o orçamento **não pode mais ser editado**. Se precisar corrigir, cancele e crie um novo.

---

## 7. Ordens de Serviço (OS)

### O que é

A Ordem de Serviço é o documento de trabalho da oficina. Ela controla tudo que acontece com o veículo: o defeito relatado, o diagnóstico, os serviços realizados, as peças utilizadas e o pagamento.

### Ciclo de vida de uma OS

```
Aberta → Em Andamento → Aguardando → Concluída → Entregue
                          (peça/aprovação)
```
Em qualquer etapa a OS pode ser **Cancelada**.

### Como abrir uma OS

**Opção mais rápida:** Na ficha do veículo, clique em **Nova OS** — cliente e veículo já vêm preenchidos.

**Opção pelo menu:** Clique em **Ordens de Serviço** → **Nova OS**.

Campos obrigatórios:
- **Cliente** e **Veículo**
- **Defeito Relatado** — descreva exatamente o que o cliente relatou
- Preencha **KM de Entrada**, **Mecânico** responsável e **Data de Previsão** se souber

Após salvar, adicione os serviços e peças previstas nas seções da página de edição.

### Adicionando serviços e peças na OS

Após a OS estar aberta (status: Aberta, Em Andamento ou Aguardando):

1. No detalhe da OS, clique no botão **+ Adicionar** no cabeçalho da seção **Serviços** ou **Peças**
2. Na janela que abre:
   - Para **serviço**: selecione o tipo (preenche automaticamente) ou escreva diretamente
   - Para **peça**: selecione o produto do estoque (preenche automaticamente)
   - Ajuste quantidade e preço se necessário
3. Clique em **Adicionar** — o item aparece imediatamente na tabela e os totais são atualizados

> Você também pode ir em **Editar** para adicionar múltiplos itens de uma vez usando o formulário completo.

### Avançando o status da OS

| Botão | Condição | O que acontece |
|---|---|---|
| **Iniciar** | Status: Aberta | Muda para "Em Andamento" |
| **Concluir** | Status: Em Andamento ou Aguardando | Muda para "Concluída" |
| **Entregar** | Status: Concluída | Abre janela para informar KM de saída e confirmar entrega |
| **Cancelar** | Qualquer status ativo | Cancela a OS com confirmação |

### Registrando o pagamento

Após a OS estar **Concluída** ou **Entregue**, o formulário de pagamento aparece na coluna esquerda:

1. Confirme ou ajuste o **valor pago**
2. Selecione a **forma de pagamento**
3. Clique em **Confirmar Pagamento**

O sistema cria automaticamente um lançamento de receita no módulo Financeiro.

### Lista de OS — alertas visuais

Na lista de OS, linhas em **vermelho** indicam ordens com data de previsão vencida e ainda em aberto. O banner no topo mostra o total de OS atrasadas.

---

## 8. Estoque

### O que é

O módulo de estoque controla as peças, lubrificantes e materiais da oficina. Quando uma peça é usada em uma OS ou orçamento, o preço de venda é sugerido automaticamente.

### Cadastro de produto

1. Menu lateral → **Produtos** → **Novo Produto**
2. Preencha:
   - **Código**: referência interna
   - **Nome**, **Categoria** e **Fornecedor**
   - **Preço de Custo** e **Margem de Lucro** → o **Preço de Venda** é calculado automaticamente
   - **Estoque Mínimo** → quando o estoque atual ficar abaixo desse valor, um alerta aparece no dashboard
   - **Quantidade Inicial** → na criação, registre o estoque atual

### Movimentações de estoque

Use o menu **Movimentações** para registrar:
- **Entrada**: compra de peças do fornecedor
- **Saída**: retirada avulsa (perda, uso interno, etc.)

> As peças utilizadas em OS **não** debitam o estoque automaticamente. O controle de estoque e de OS são independentes — registre as saídas manualmente quando necessário.

### Alertas de estoque

Quando um produto estiver abaixo do estoque mínimo:
- Aparece um badge **Alerta** vermelho na lista de produtos
- O dashboard exibe a quantidade de produtos em alerta
- Acesse **Alertas de Estoque** no menu para ver apenas os produtos críticos

---

## 9. Financeiro

### O que é

O módulo financeiro registra todas as entradas (receitas) e saídas (despesas) da oficina. Diferente do caixa diário, ele trabalha com o conceito de **competência** — o lançamento pertence ao mês em que o serviço ocorreu, independente de quando o pagamento foi recebido.

### Conceito de Data de Competência

> A **Data de Competência** é a data em que o fato aconteceu (quando o serviço foi prestado ou quando a conta foi gerada), não a data do pagamento.
>
> **Exemplo:** Aluguel de abril pago em 5 de maio → competência: 30/04, pagamento: 05/05. No relatório de abril, a despesa aparece. No fluxo de caixa de maio, a saída aparece.

### Como criar um lançamento

1. Menu lateral → **Lançamentos** → **Novo Lançamento**
2. Escolha obrigatoriamente **Receita** ou **Despesa** no campo Tipo
   > O sistema sugere automaticamente o tipo ao selecionar a categoria (ex: Aluguel → Despesa)
3. Preencha a **Categoria**, **Descrição** e **Valor**
4. Informe a **Data de Competência** (obrigatório), **Vencimento** e **Data de Pagamento** (quando pago)
5. Clique em **Salvar Lançamento**

### Marcar como pago

Na lista de lançamentos, lançamentos **Pendentes** têm um botão verde (✓) na coluna de ações. Clique nele para marcar como pago instantaneamente — a data de pagamento é registrada automaticamente.

### Fluxo de Caixa

O **Fluxo de Caixa** mostra todos os lançamentos de um mês selecionado com os totais de receitas, despesas e saldo. Use os filtros de mês e ano para navegar entre períodos.

---

## 10. Relatórios

### Dashboard

Tela inicial com visão geral da oficina. Veja a seção [Dashboard](#3-dashboard--painel-principal).

### Faturamento

Relatório financeiro mensal com filtros por tipo (receita/despesa) e status. Exibe:
- KPIs de receitas pagas, pendentes, despesas pagas e saldo
- Gráfico diário de receitas e despesas
- Tabela detalhada de lançamentos

Use as setas **◄ ►** para navegar entre meses.

### Orçamentos

Análise dos orçamentos por período: total criado, aprovados, reprovados e pendentes.

### Serviços

- **Serviços mais realizados**: ranking dos tipos de serviço por quantidade de execuções
- **Clientes mais frequentes**: ranking de clientes por número de OS

---

## 11. Meu Perfil

Acesse seu perfil clicando em **Perfil** no rodapé do menu lateral.

### O que você pode alterar

- **Usuário** (login)
- **Nome completo**
- **E-mail** e **Telefone**
- **Foto de perfil** (avatar)

### O que não pode ser alterado pelo próprio usuário

- **Perfil de acesso** (Administrador, Mecânico, Recepcionista) — apenas o Administrador pode alterar isso

### Alterar senha

Clique no botão **Alterar Senha** no topo da página de perfil.

---

## 12. Fluxos Completos — Passo a Passo

### Fluxo 1: Cliente novo traz carro para revisão (sem orçamento)

1. **Cadastrar cliente** (se ainda não existir): Clientes → Novo Cliente
2. **Cadastrar veículo**: na ficha do cliente → Novo Veículo
3. **Abrir OS**: na ficha do veículo → Nova OS
4. Preencher **defeito relatado**, **KM de entrada** e **mecânico**
5. Salvar e **Iniciar** a OS
6. No detalhe da OS, **adicionar serviços** e **peças** conforme o serviço é realizado
7. **Concluir** a OS quando o trabalho terminar
8. **Entregar** o veículo (informar KM de saída)
9. **Registrar pagamento** na OS

---

### Fluxo 2: Cliente solicita orçamento antes de aprovar o serviço

1. **Abrir orçamento**: Orçamentos → Novo Orçamento
2. Selecionar **cliente** e **veículo**
3. Adicionar **serviços** e **peças** com valores
4. **Enviar ao Cliente** (muda status para Enviado)
5. Aguardar resposta do cliente:
   - **Cliente aprovou** → botão **Aprovar** → botão **Gerar OS**
   - **Cliente reprovou** → botão **Mais ações** → Reprovar
6. Com a OS gerada, prossiga a partir do passo 5 do Fluxo 1

---

### Fluxo 3: Registrar uma despesa (ex: compra de peças)

1. Menu → **Lançamentos** → **Novo Lançamento**
2. **Tipo**: Despesa (ou selecione a categoria "Fornecedor / Compra" e o sistema sugere automaticamente)
3. **Categoria**: Fornecedor / Compra
4. Preencher descrição, valor e datas
5. Se a compra já foi paga: preencher **Data de Pagamento** e colocar status **Pago / Recebido**
6. Se ainda não pagou: deixar status **Pendente**

---

### Fluxo 4: Entrada de peças no estoque

1. Menu → **Movimentações** → botão **Nova Movimentação** (ou pelo menu Estoque)
2. Selecionar o **produto**
3. **Tipo**: Entrada
4. Informar **quantidade** e **custo unitário**
5. Preencher número da **nota fiscal** se houver
6. Salvar — o estoque do produto é atualizado automaticamente

---

## 13. Permissões por Perfil

| Funcionalidade | Administrador | Recepcionista | Mecânico |
|---|---|---|---|
| Clientes — visualizar/criar/editar | ✅ | ✅ | — |
| Clientes — desativar | ✅ | ✅ | — |
| Veículos — todos | ✅ | ✅ | — |
| Orçamentos — todos | ✅ | ✅ | — |
| OS — visualizar | ✅ | ✅ | ✅ |
| OS — criar/editar | ✅ | ✅ | — |
| OS — atualizar status | ✅ | ✅ | ✅ |
| OS — registrar pagamento | ✅ | ✅ | — |
| Estoque — produtos | ✅ | ✅ | — |
| Estoque — movimentações | ✅ | ✅ | — |
| Financeiro — lançamentos | ✅ | ✅ | — |
| Financeiro — excluir lançamentos | ✅ | — | — |
| Relatórios — faturamento/orçamentos/serviços | ✅ | — | — |
| Usuários — gerenciar | ✅ | — | — |
| Formas de pagamento — gerenciar | ✅ | — | — |
| Tipos de serviço — gerenciar | ✅ | — | — |
| Marcas e modelos — gerenciar | ✅ | — | — |

---

## 14. Dicas e Boas Práticas

### Cadastro de clientes
- Sempre verifique se o cliente já existe antes de cadastrar um novo (use a busca por telefone ou CPF)
- Preencha o CEP para que o endereço seja preenchido automaticamente
- Um cliente inativo nunca aparece nos formulários de OS ou orçamento — se um cliente voltou após ser desativado, clique em **Reativar**

### Orçamentos
- Use o campo **Condições / Garantia** para registrar o prazo de garantia dos serviços
- Orçamentos aprovados geram OS com todos os itens — evite gerar a OS antes de ter certeza que o cliente aprovou
- Orçamentos a vencer aparecem no dashboard nos 7 dias anteriores ao vencimento

### Ordens de Serviço
- Preencha sempre o **Defeito Relatado** com as palavras do próprio cliente — isso é importante em caso de disputas
- Use o campo **Diagnóstico** para registrar o que o mecânico identificou
- Informe o **KM de saída** na entrega para manter o histórico de quilometragem do veículo
- Uma OS com prazo de previsão vencido aparece com linha vermelha na lista — monitore diariamente

### Financeiro
- Lançamentos gerados automaticamente pelo pagamento de OS têm a descrição preenchida como "OS-XXXXXX — Nome do Cliente"
- Use a **Data de Competência** para registrar quando o serviço ocorreu, mesmo que o pagamento seja futuro
- Marque lançamentos como pagos conforme o dinheiro entrar — isso mantém o fluxo de caixa fiel à realidade

### Estoque
- Defina sempre o **Estoque Mínimo** — o sistema alerta automaticamente quando uma peça precisa ser reposta
- Use o campo **Localização** para anotar onde a peça fica fisicamente na oficina

---

*Manual do Usuário — Oficina-Gest v1.0*  
*Desenvolvido por Leandro Lopes*
