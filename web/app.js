"use strict";
const $ = (id) => document.getElementById(id);
let chave = "", estadoServidor = null, catalogo = [], tarefaAtual = null, pedidoPendente = null, enviando = false, versaoSessao = 0, atualizando = false;
const nomesStatus = {pendente:"Aguardando executor", executando:"Em execução", concluida:"Concluída pela rotina", falha:"Falhou", recusada:"Pré-condição recusada", nao_confirmada:"Resultado não confirmado", interrompida:"Interrompida"};
const nomesEtapas = {navegar_menu:"Navegar pelo menu", preencher_periodo:"Preencher período", identificar_formulario:"Identificar formulário", gerar_documento:"Gerar documento", encerrar:"Encerrar e conferir retorno", validar_dados:"Validar dados", identificar_empresa:"Identificar empresa", abrir_livros:"Abrir Livros Fiscais", gerar_previa:"Gerar prévia", exportar_pdf:"Exportar PDF", conferir_pdf:"Conferir PDF", recuperar_interface:"Recuperar interface", fim:"Resultado da rotina"};
const estados = {inicio:"Em andamento", confirmado:"Confirmado", acao_executada:"Ação enviada", resultado_nao_verificado:"Não verificado", inconclusivo:"Inconclusivo", falha:"Falhou", concluido:"Concluído pela rotina"};
const etapasGeracao = ["navegar_menu","preencher_periodo","identificar_formulario","gerar_documento","encerrar"];
const etapasLivros = ["validar_dados","identificar_empresa","abrir_livros","preencher_periodo","gerar_previa","exportar_pdf","conferir_pdf","encerrar"];
const motivos = {calibracao_indisponivel:"Calibre a tela principal no servidor.", dominio_fora_de_foco:"Deixe o Domínio visível na sessão do servidor.", tela_principal_nao_confirmada:"Confira a tela principal do Domínio no servidor.", empresa_nao_confirmada:"A empresa no servidor não corresponde ao código solicitado.", periodo_nao_confirmado:"Confira o período solicitado.", servidor_reiniciado:"O servidor reiniciou; confira o Domínio antes de uma nova execução.", erro_execucao_consulte_servidor:"Consulte o log local do servidor.", resultado_ou_retorno_nao_confirmado:"O resultado ou retorno não foi confirmado; confira o servidor.", executor_requer_windows:"O executor precisa de uma sessão Windows.", precondicao_nao_confirmada:"Confira as condições da sessão do servidor."};

function aviso(texto) { $("aviso").textContent = texto; }
function conectado(online) { $("conexao").textContent = online ? "Servidor conectado" : "Desconectado"; $("conexao").classList.toggle("online", online); }
async function api(caminho, opcoes = {}) {
  const credencial=chave, controlador=new AbortController(), limite=setTimeout(()=>controlador.abort(),10000);
  try {
    const resposta = await fetch(`/api/${caminho}`, {...opcoes, headers:{"Authorization":`Bearer ${credencial}`, "Content-Type":"application/json", ...opcoes.headers}, cache:"no-store", signal:controlador.signal});
    if (!resposta.ok) {const dados = await resposta.json().catch(()=>({})); if (resposta.status===401 && chave===credencial) desconectar(); throw new Error(dados.detail || "Não foi possível obter o resultado do servidor.");}
    return await resposta.json();
  } catch (erro) {if (erro.name==="AbortError") throw new Error("O servidor não respondeu no prazo. Confira o histórico antes de repetir."); throw erro;}
  finally {clearTimeout(limite);}
}
function desconectar() {
  versaoSessao++; chave=""; estadoServidor=null; tarefaAtual=null; pedidoPendente=null; catalogo=[];
  $("conteudo").hidden=true; $("sair").hidden=true; $("login").hidden=false; conectado(false);
  $("form-tarefa").reset(); $("capacidade").replaceChildren(); $("estados").replaceChildren(); $("historico").replaceChildren(); $("chave").value="";
  $("resultado").textContent="Aguardando seleção"; $("tarefa-detalhe").textContent="Selecione uma execução no histórico."; $("baixar").hidden=true; $("progresso").value=0;
}
function atualizarCampos() {
  const item = catalogo.find((c)=>c.id===$("capacidade").value);
  $("descricao").textContent = item ? item.periodo+(item.id.startsWith("registro_") ? " A conferência do período no PDF está pendente nesta versão." : "") : "";
  const automatico = !$("capacidade").value.startsWith("registro_");
  for (const nome of ["inicio","fim"]) {$(nome).disabled=automatico; if (automatico && estadoServidor) $(nome).value=estadoServidor.periodo_anterior[nome];}
}
function atualizarBotao() {$("executar").disabled = enviando || !estadoServidor || !estadoServidor.execucao_habilitada || estadoServidor.ocupado;}
function celula(linha, texto) {const td=document.createElement("td"); td.textContent=texto; linha.append(td); return td;}
function exibirHistorico(tarefas) {
  $("historico").replaceChildren(); $("vazio").hidden=!!tarefas.length;
  for (const tarefa of tarefas) {
    const linha=document.createElement("tr");
    linha.classList.toggle("selecionada",tarefa.id===tarefaAtual);
    celula(linha, new Date(tarefa.criado).toLocaleString("pt-BR"));
    const nome=catalogo.find((c)=>c.id===tarefa.pedido.capacidade)?.nome || "Rotina";
    celula(linha, nome+(tarefa.modo==="simulacao" ? " (simulada)" : ""));
    celula(linha, tarefa.pedido.empresa_codigo);
    celula(linha, nomesStatus[tarefa.status] || "Não confirmado").className=tarefa.status;
    const botao=document.createElement("button"); botao.textContent="Ver"; botao.className="secundario";
    botao.addEventListener("click",()=>{tarefaAtual=tarefa.id; acompanhar().catch(erro=>aviso(erro.message));}); celula(linha,"").append(botao);
    $("historico").append(linha);
  }
  $("ultimo").textContent=tarefas.length ? nomesStatus[tarefas[0].status] || "Não confirmado" : "Nenhuma execução";
}
async function acompanhar() {
  if (!tarefaAtual) return;
  const identificador=tarefaAtual, versao=versaoSessao;
  const tarefa=await api(`tarefas/${identificador}`);
  if (versao!==versaoSessao || identificador!==tarefaAtual) return;
  const linhas=new Map(); let execucao=null, tentativa=null;
  for (const ev of tarefa.eventos) {
    if (ev.execution_id!==execucao || ev.attempt!==tentativa) {linhas.clear(); execucao=ev.execution_id; tentativa=ev.attempt;}
    linhas.set(ev.step,ev);
  }
  $("resultado").textContent=(tarefa.modo==="simulacao" ? "Teste simulado — " : "")+(nomesStatus[tarefa.status] || "Resultado não confirmado");
  $("resultado").className=`resultado ${tarefa.status}`;
  const nome=catalogo.find(c=>c.id===tarefa.pedido.capacidade)?.nome || "Rotina";
  const data=text=>text.split("-").reverse().join("/");
  $("tarefa-detalhe").textContent=`${nome} · Empresa ${tarefa.pedido.empresa_codigo} · ${data(tarefa.pedido.inicio)} a ${data(tarefa.pedido.fim)}${tentativa ? ` · Tentativa ${tentativa}` : ""}`;
  const retorno=[...linhas.values()].some(ev=>["encerrar","recuperar_interface"].includes(ev.step) && ev.status==="confirmado" && ev.evidence==="tela_principal_reconhecida");
  $("retorno").textContent=`Retorno à tela principal: ${retorno ? "confirmado" : "não confirmado"}.`;
  const etapas=tarefa.pedido.capacidade.startsWith("registro_") ? etapasLivros : etapasGeracao;
  $("progresso").max=etapas.length; $("progresso").value=etapas.filter(etapa=>linhas.get(etapa)?.status==="confirmado").length;
  $("estados").replaceChildren();
  for (const etapa of [...etapas,...["recuperar_interface","fim"].filter(e=>linhas.has(e))]) {
    const ev=linhas.get(etapa), linha=document.createElement("tr"); celula(linha,nomesEtapas[etapa]); celula(linha,ev ? estados[ev.status] : "Aguardando").className=ev?.status || "";
    celula(linha,ev ? `${ev.elapsed_seconds.toFixed(1)} s` : "—"); $("estados").append(linha);
  }
  $("baixar").hidden=!tarefa.arquivo_disponivel;
  if (tarefa.motivo) aviso(motivos[tarefa.motivo] || "Confira o resultado no servidor.");
}
async function atualizar() {
  if (!chave || atualizando) return;
  atualizando=true; const versao=versaoSessao;
  try {
    const [estado, tarefas]=await Promise.all([api("estado"),api("tarefas")]);
    if (versao!==versaoSessao) return;
    if (estadoServidor && JSON.stringify(estado.periodo_anterior)!==JSON.stringify(estadoServidor.periodo_anterior)) $("apuracao").checked=false;
    estadoServidor=estado; conectado(true); atualizarCampos();
    $("modo").textContent={consulta:"Somente consulta",windows:"Executor Windows",simulacao:"Teste simulado"}[estado.modo] || "Servidor";
    $("sessao").textContent=estado.ocupado ? "Execução em andamento" : "Disponível";
    if (estado.modo==="simulacao") aviso("Modo simulado: este teste não opera o Domínio nem gera documentos fiscais.");
    else if (!estado.execucao_habilitada) aviso("O servidor está em consulta. O responsável precisa habilitar o executor para receber comandos.");
    const localizada=pedidoPendente && tarefas.find(t=>t.pedido.request_id===pedidoPendente.request_id);
    if (localizada) {tarefaAtual=localizada.id; pedidoPendente=null;}
    if (!tarefaAtual && tarefas.length) tarefaAtual=tarefas[0].id;
    exibirHistorico(tarefas);
    atualizarBotao(); await acompanhar();
  } catch (erro) {if (versao===versaoSessao) {estadoServidor=null; conectado(false); atualizarBotao(); aviso(`Conexão ou resultado indisponível. ${erro.message}`);}}
  finally {atualizando=false;}
}
$("form-login").addEventListener("submit",async(e)=>{
  e.preventDefault(); chave=$("chave").value.trim();
  versaoSessao++;
  try {estadoServidor=await api("estado"); catalogo=await api("capacidades"); $("capacidade").replaceChildren();
    for (const item of catalogo) {const opcao=document.createElement("option"); opcao.value=item.id; opcao.textContent=item.nome; $("capacidade").append(opcao);}
    $("chave").value=""; $("login").hidden=true; $("conteudo").hidden=false; $("sair").hidden=false;
    for (const nome of ["inicio","fim"]) $(nome).value=estadoServidor.periodo_anterior[nome]; atualizarCampos(); aviso(""); await atualizar();
  } catch (erro) {chave=""; aviso(erro.message);}
});
$("capacidade").addEventListener("change",atualizarCampos); $("sair").addEventListener("click",()=>{desconectar(); aviso("");});
for (const nome of ["capacidade","empresa","inicio","fim"]) $(nome).addEventListener("input",()=>{$("apuracao").checked=false;});
$("form-tarefa").addEventListener("submit",async(e)=>{
  e.preventDefault(); if (enviando || !estadoServidor || !estadoServidor.execucao_habilitada || estadoServidor.ocupado) return;
  const dados={capacidade:$("capacidade").value,empresa_codigo:$("empresa").value.trim(),inicio:$("inicio").value,fim:$("fim").value,apuracao_confirmada:$("apuracao").checked};
  if (!pedidoPendente || JSON.stringify(dados)!==JSON.stringify(pedidoPendente.dados)) pedidoPendente={dados,request_id:crypto.randomUUID()};
  enviando=true; atualizarBotao();
  try {const tarefa=await api("tarefas",{method:"POST",body:JSON.stringify({...dados,request_id:pedidoPendente.request_id})}); tarefaAtual=tarefa.id; pedidoPendente=null; aviso(""); await atualizar();}
  catch (erro) {aviso(`${erro.message} Confira o histórico antes de repetir; uma nova tentativa com os mesmos campos reutiliza o identificador.`);}
  finally {enviando=false; atualizarBotao();}
});
$("baixar").addEventListener("click",async()=>{
  try {const resposta=await fetch(`/api/tarefas/${tarefaAtual}/arquivo`,{headers:{"Authorization":`Bearer ${chave}`},cache:"no-store"}); if (!resposta.ok) throw new Error("Arquivo indisponível.");
    const disposicao=resposta.headers.get("Content-Disposition") || "", unicode=disposicao.match(/filename\*=utf-8''([^;]+)/i), normal=disposicao.match(/filename="([^"]+)"/i);
    const nome=unicode ? decodeURIComponent(unicode[1]) : normal ? normal[1] : `documento_${tarefaAtual}.pdf`;
    const url=URL.createObjectURL(await resposta.blob()), link=document.createElement("a"); link.href=url; link.download=nome; link.click(); URL.revokeObjectURL(url);
  } catch (erro) {aviso(erro.message);}
});
let instalacao=null;
window.addEventListener("beforeinstallprompt",(e)=>{e.preventDefault(); instalacao=e; $("instalar").hidden=false;});
$("instalar").addEventListener("click",async()=>{if (!instalacao) return; await instalacao.prompt(); await instalacao.userChoice; instalacao=null; $("instalar").hidden=true;});
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(()=>{});
window.addEventListener("offline",()=>{estadoServidor=null; conectado(false); atualizarBotao(); aviso("Sem conexão. Nenhuma nova tarefa será enviada; o resultado será consultado quando a conexão voltar.");});
setInterval(atualizar,2000);
