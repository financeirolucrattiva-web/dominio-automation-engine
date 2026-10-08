"use strict";
const $ = (id) => document.getElementById(id);
let chave = "", estadoServidor = null, catalogo = [], tarefaAtual = null, pedidoPendente = null, enviando = false, versaoSessao = 0, atualizando = false, leituraAtual = 0, conectando = false, controlando = false, configurando = false, solicitacaoCodigo = null, capturaPendente = false, limiteCaptura = null;
const nomesStatus = {pendente:"Aguardando executor", executando:"Em execução", concluida:"Concluída pela rotina", falha:"Falhou", recusada:"Pré-condição recusada", nao_confirmada:"Resultado não confirmado", interrompida:"Interrompida"};
const nomesEtapas = {navegar_menu:"Navegar pelo menu", preencher_periodo:"Preencher período", identificar_formulario:"Identificar formulário", gerar_documento:"Gerar documento", encerrar:"Encerrar e conferir retorno", validar_dados:"Validar dados", identificar_empresa:"Identificar empresa", abrir_livros:"Abrir Livros Fiscais", gerar_previa:"Gerar prévia", exportar_pdf:"Exportar PDF", conferir_pdf:"Conferir PDF", recuperar_interface:"Recuperar interface", fim:"Resultado da rotina"};
const estados = {inicio:"Em andamento", confirmado:"Confirmado", acao_executada:"Ação enviada", resultado_nao_verificado:"Não verificado", inconclusivo:"Inconclusivo", falha:"Falhou", concluido:"Concluído pela rotina"};
const etapasGeracao = ["navegar_menu","preencher_periodo","identificar_formulario","gerar_documento","encerrar"];
const etapasLivros = ["validar_dados","identificar_empresa","abrir_livros","preencher_periodo","gerar_previa","exportar_pdf","conferir_pdf","encerrar"];
const motivos = {calibracao_indisponivel:"Calibre a tela principal no servidor.", dominio_fora_de_foco:"Deixe o Domínio visível na sessão do servidor.", tela_principal_nao_confirmada:"Confira a tela principal do Domínio no servidor.", empresa_nao_confirmada:"A empresa no servidor não corresponde ao código solicitado.", periodo_nao_confirmado:"Confira o período solicitado.", servidor_reiniciado:"O servidor reiniciou; confira o Domínio antes de uma nova execução.", erro_execucao_consulte_servidor:"Consulte o log local do servidor.", resultado_ou_retorno_nao_confirmado:"O resultado ou retorno não foi confirmado; confira o servidor.", executor_requer_windows:"O executor precisa de uma sessão Windows.", precondicao_nao_confirmada:"Confira as condições da sessão do servidor."};

function aviso(texto) { $("aviso").textContent = texto; }
function conectado(online) { $("conexao").textContent = online ? "Servidor conectado" : "Desconectado"; $("conexao").classList.toggle("online", online); }
function selecionarTarefa(identificador) {
  if (tarefaAtual===identificador) return;
  tarefaAtual=identificador; leituraAtual++;
  $("resultado").textContent=identificador ? "Consultando execução…" : "Aguardando seleção";
  $("resultado").className="resultado"; $("tarefa-detalhe").textContent="Selecione uma execução no histórico.";
  $("tarefa-detalhe").dataset.tarefaId=identificador || "";
  $("retorno").textContent="Retorno à tela principal: ainda não observado.";
  $("estados").replaceChildren(); $("baixar").hidden=true; $("progresso").value=0;
  $("motivo-tarefa").textContent=""; atualizarControle();
}
async function api(caminho, opcoes = {}) {
  const credencial=chave, versao=versaoSessao, controlador=new AbortController(), limite=setTimeout(()=>controlador.abort(),10000);
  try {
    const resposta = await fetch(`/api/${caminho}`, {...opcoes, headers:{"Authorization":`Bearer ${credencial}`, "Content-Type":"application/json", ...opcoes.headers}, cache:"no-store", signal:controlador.signal});
    if (!resposta.ok) {const dados = await resposta.json().catch(()=>({})); if (resposta.status===401 && chave===credencial && versao===versaoSessao) {desconectar(); aviso("Acesso não autorizado. Confira a chave do servidor.");} throw new Error(dados.detail || "Não foi possível obter o resultado do servidor.");}
    return await resposta.json();
  } catch (erro) {if (erro.name==="AbortError") throw new Error("O servidor não respondeu no prazo. Confira o histórico antes de repetir."); throw erro;}
  finally {clearTimeout(limite);}
}
function desconectar() {
  versaoSessao++; chave=""; estadoServidor=null; selecionarTarefa(null); pedidoPendente=null; catalogo=[];
  painelLotes.limpar();
  $("conteudo").hidden=true; $("sair").hidden=true; $("login").hidden=false; conectado(false);
  $("form-tarefa").reset(); $("capacidade").replaceChildren(); $("estados").replaceChildren(); $("historico").replaceChildren(); $("chave").value="";
  $("resultado").textContent="Aguardando seleção"; $("tarefa-detalhe").textContent="Selecione uma execução no histórico."; $("baixar").hidden=true; $("progresso").value=0;
  $("modo").textContent="—"; $("sessao").textContent="—"; $("ultimo").textContent="Nenhuma execução";
  $("form-dominio").reset(); $("form-codigo").reset(); $("form-codigo").hidden=true; solicitacaoCodigo=null; atualizarLogin();
  ocultarCaptura();
  $("form-rotina").reset(); $("rotina-passos").replaceChildren(); $("rotinas-configuradas").replaceChildren(); $("rotina-aviso").textContent=""; adicionarPasso();
}
function atualizarCampos() {
  const item = catalogo.find((c)=>c.id===$("capacidade").value);
  $("descricao").textContent = item ? item.periodo+(item.id.startsWith("registro_") ? " A conferência do período no PDF está pendente nesta versão." : "") : "";
  const competencia = item?.tipo_periodo==="competencia";
  $("campo-competencia").hidden=!competencia; $("competencia").disabled=!competencia;
  $("campo-datas").hidden=competencia;
  for (const nome of ["inicio","fim"]) {$(nome).disabled=competencia; $(nome).max=estadoServidor?.periodo_anterior.fim || "";}
  $("competencia").max=estadoServidor?.periodo_anterior.inicio.slice(0,7) || "";
  const periodo=periodoSelecionado();
  $("periodo-competencia").textContent=periodo ? `Período: ${periodo.inicio.split("-").reverse().join("/")} a ${periodo.fim.split("-").reverse().join("/")}` : "Escolha a competência no calendário.";
}
function periodoSelecionado() {
  if (catalogo.find(c=>c.id===$("capacidade").value)?.tipo_periodo!=="competencia") return $("inicio").value && $("fim").value ? {inicio:$("inicio").value,fim:$("fim").value} : null;
  const mes=$("competencia").value;
  if (!/^[0-9]{4}-(0[1-9]|1[0-2])$/.test(mes) || mes.startsWith("0000")) return null;
  const ultimo=new Date(`${mes}-01T00:00:00Z`); ultimo.setUTCMonth(ultimo.getUTCMonth()+1); ultimo.setUTCDate(0);
  return {inicio:`${mes}-01`,fim:ultimo.toISOString().slice(0,10)};
}
function atualizarControle() {
  const controle=estadoServidor?.controle_execucao;
  const ativo=!!chave && navigator.onLine && controle?.tarefa_id===tarefaAtual;
  $("pausar").hidden=!ativo; $("pausar").disabled=controlando || controle?.estado==="pausa_solicitada";
  $("pausar").textContent=controle?.estado==="pausada" ? "Continuar execução" : controle?.estado==="pausa_solicitada" ? "Pausa solicitada…" : "Pausar execução";
  $("controle-aviso").textContent=!ativo ? "" : controle.estado==="pausada" ? "Execução pausada. Mantenha a tela do servidor para continuar." : controle.estado==="pausa_solicitada" ? "Aguardando a ação atual terminar para pausar." : "";
}
function atualizarBotao() {$("executar").disabled = enviando || !estadoServidor || !estadoServidor.execucao_habilitada || estadoServidor.ocupado; atualizarControle(); atualizarLogin(); painelLotes.controles();}

const fasesLogin={nao_iniciado:"Login não iniciado",na_fila:"Aguardando a ação atual terminar",preparando_navegador:"Preparando o navegador no servidor",abrir_onvio:"Abrindo Onvio",credenciais_onvio:"Entrando no Onvio",selecionar_email:"Selecionando verificação por e-mail",aguardando_codigo:"Aguardando seu código de verificação",verificando_codigo:"Verificando o código",abrir_dominioweb:"Abrindo Domínio Web",abrir_escrita_fiscal:"Abrindo Escrita Fiscal",credenciais_dominio:"Entrando no Domínio",conferir_tela_principal:"Conferindo a tela principal",tela_principal_confirmada:"Tela principal do Domínio confirmada",calibrando_tela:"Medindo a tela principal",calibracao_confirmada:"Referência da tela principal salva",fechando_ciclo:"Fechando o ciclo anterior",cancelado:"Login cancelado",falha:"Login ou calibração não confirmado"};
const motivosLogin={navegador_indisponivel:"Instale Edge ou Chrome no servidor.",destino_nao_permitido:"A página mudou para um endereço que não está configurado.",tela_login_nao_reconhecida:"A tela esperada não foi reconhecida. Confira a etapa indicada e a sessão do servidor.",campos_login_nao_confirmados:"Os campos do login Fiscal não foram reconhecidos com segurança.",janela_login_nao_confirmada:"Não reconheci uma janela do cliente Domínio em foco.",calibracao_nao_confirmada:"Deixe a tela principal azul, maximizada e sem menus, e use Calibrar tela principal.",fechamento_nao_confirmado:"Uma janela não confirmou o fechamento. O RPA não iniciou outro ciclo.",codigo_expirado:"O código não foi informado no prazo. Inicie uma nova tentativa.",login_nao_confirmado:"O acesso não foi confirmado. A rotina fiscal não será iniciada automaticamente.",login_cancelado:"A tentativa foi cancelada."};
function atualizarLogin() {
  const login=estadoServidor?.login, permitido=!!chave && navigator.onLine && login?.disponivel;
  const ativo=login && !["nao_iniciado","tela_principal_confirmada","calibracao_confirmada","captura_pronta","falha","cancelado"].includes(login.estado);
  $("entrar-dominio").disabled=!permitido || configurando || !!estadoServidor?.ocupado;
  $("reiniciar-ciclo").disabled=!permitido || configurando || !!ativo;
  $("cancelar-login").hidden=!permitido || !ativo; $("cancelar-login").disabled=configurando;
  $("calibrar-servidor").disabled=!permitido || configurando || !!estadoServidor?.ocupado;
  $("capturar-servidor").disabled=!permitido || configurando || !!estadoServidor?.ocupado;
  $("login-estado").textContent=login ? (fasesLogin[login.estado] || "Estado não reconhecido")+(login.estado==="falha" ? ` · Etapa: ${fasesLogin[login.etapa] || "não reconhecida"}` : "")+(login.motivo ? ` · ${motivosLogin[login.motivo] || "Confira o servidor."}` : "") : "Conecte ao servidor para configurar o acesso.";
  const codigo=permitido && login.estado==="aguardando_codigo" && !!login.solicitacao_id;
  if (solicitacaoCodigo!==login?.solicitacao_id) {$("codigo").value=""; solicitacaoCodigo=login?.solicitacao_id || null;}
  $("form-codigo").hidden=!codigo;
  $("form-codigo").querySelector("button").disabled=configurando;
  $("codigo-prazo").textContent=codigo ? `Informe o código em até ${login.segundos_restantes} segundos. Ele será usado uma vez.` : "";
  if (codigo) $("config-login").open=true;
}

async function configurar(caminho, dados) {
  if (configurando || !estadoServidor || !navigator.onLine) return;
  const versao=versaoSessao;
  configurando=true; atualizarLogin();
  try {await api(caminho,{method:"POST",...(dados ? {body:JSON.stringify(dados)} : {})});
    if (versao===versaoSessao) {aviso(""); await atualizar(); return true;}
  } catch (erro) {if (versao===versaoSessao) aviso(erro.message);}
  finally {configurando=false; atualizarLogin();}
  return false;
}

function dadosLogin() {
  return {email:$("onvio-email").value.trim(),senha_onvio:$("onvio-senha").value,usuario_dominio:$("dominio-usuario").value.trim(),senha_dominio:$("dominio-senha").value,confirmar_reinicio:$("confirmar-reinicio").checked};
}
async function entrarDominio(reiniciar) {
  if (!$("form-dominio").reportValidity()) return;
  if (reiniciar && !$("confirmar-reinicio").checked) {aviso("Confirme o fechamento do ciclo para reiniciar."); return;}
  const dados=dadosLogin();
  $("onvio-senha").value=$("dominio-senha").value="";
  await configurar(reiniciar ? "login/reiniciar" : "login/iniciar",dados);
  dados.senha_onvio=dados.senha_dominio="";
}
$("form-dominio").addEventListener("submit",e=>{e.preventDefault(); entrarDominio(false);});
$("reiniciar-ciclo").addEventListener("click",()=>entrarDominio(true));
$("cancelar-login").addEventListener("click",()=>configurar("login/cancelar"));
$("form-codigo").addEventListener("submit",async e=>{
  e.preventDefault(); if (!solicitacaoCodigo || !$("form-codigo").reportValidity()) return;
  const dados={solicitacao_id:solicitacaoCodigo,codigo:$("codigo").value}; $("codigo").value="";
  await configurar("login/codigo",dados); dados.codigo="";
});
$("calibrar-servidor").addEventListener("click",()=>{
  if (!$("confirmar-calibracao").checked) {aviso("Confirme que o Domínio está na tela principal azul antes de calibrar."); return;}
  $("confirmar-calibracao").checked=false;
  configurar("sessao/calibrar",{tela_principal_confirmada:true});
});
fasesLogin.capturando_tela="Capturando a janela do Domínio"; fasesLogin.captura_pronta="Captura disponível para conferência";
function ocultarCaptura() {capturaPendente=false; clearTimeout(limiteCaptura); $("captura-servidor").hidden=true; $("captura-servidor").removeAttribute("src"); $("ocultar-captura").hidden=true;}
$("ocultar-captura").addEventListener("click",ocultarCaptura);
$("capturar-servidor").addEventListener("click",async()=>{
  ocultarCaptura(); capturaPendente=true;
  if (!await configurar("sessao/capturar")) capturaPendente=false;
});
async function exibirCaptura() {
  if (!capturaPendente || estadoServidor?.login?.estado!=="captura_pronta") return;
  capturaPendente=false; const versao=versaoSessao;
  const controlador=new AbortController(), limite=setTimeout(()=>controlador.abort(),10000);
  try {const resposta=await fetch("/api/sessao/captura",{headers:{"Authorization":`Bearer ${chave}`},cache:"no-store",signal:controlador.signal});
    if (!resposta.ok) throw new Error("A captura expirou ou está indisponível; solicite outra.");
    const arquivo=await resposta.blob(), leitor=new FileReader();
    const url=await new Promise((resolve,reject)=>{leitor.onload=()=>resolve(leitor.result); leitor.onerror=()=>reject(new Error("Captura indisponível.")); leitor.readAsDataURL(arquivo);});
    if (versao!==versaoSessao) return;
    $("captura-servidor").src=url; $("captura-servidor").hidden=false; $("ocultar-captura").hidden=false;
    limiteCaptura=setTimeout(ocultarCaptura,30000);
  } catch (erro) {if (versao===versaoSessao) aviso(erro.message);}
  finally {clearTimeout(limite);}
}
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
    botao.addEventListener("click",()=>{selecionarTarefa(tarefa.id); acompanhar().catch(erro=>aviso(erro.message));}); celula(linha,"").append(botao);
    $("historico").append(linha);
  }
  $("ultimo").textContent=tarefas.length ? nomesStatus[tarefas[0].status] || "Não confirmado" : "Nenhuma execução";
}
async function acompanhar() {
  if (!tarefaAtual) return;
  const identificador=tarefaAtual, versao=versaoSessao, leitura=++leituraAtual;
  const tarefa=await api(`tarefas/${identificador}`);
  if (versao!==versaoSessao || identificador!==tarefaAtual || leitura!==leituraAtual) return;
  const linhas=new Map(); let execucao=null, tentativa=null;
  for (const ev of tarefa.eventos) {
    if (ev.execution_id!==execucao || ev.attempt!==tentativa) {linhas.clear(); execucao=ev.execution_id; tentativa=ev.attempt;}
    linhas.set(ev.step,ev);
  }
  $("resultado").textContent=(tarefa.modo==="simulacao" ? "Teste simulado — " : "")+(nomesStatus[tarefa.status] || "Resultado não confirmado");
  const controle=estadoServidor?.controle_execucao;
  if (controle?.tarefa_id===identificador && controle.estado!=="executando") $("resultado").textContent=controle.estado==="pausada" ? "Execução pausada" : "Pausa solicitada — aguardando ponto seguro";
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
  $("motivo-tarefa").textContent=tarefa.motivo ? motivos[tarefa.motivo] || (tarefa.motivo==="retomada_nao_confirmada" ? "A tela ou o foco mudou durante a pausa. Confira o servidor antes de uma nova tarefa." : tarefa.motivo==="servidor_encerrado_durante_pausa" ? "O servidor foi encerrado durante a pausa; a rotina foi interrompida." : "Confira o resultado no servidor.") : "";
  if (tarefa.motivo) aviso($("motivo-tarefa").textContent);
}
async function atualizar() {
  if (!chave || atualizando) return;
  atualizando=true; const versao=versaoSessao;
  try {
    const [estado, tarefas, rotinas, cadastros, lotes]=await Promise.all([api("estado"),api("tarefas"),api("rotinas"),api("cadastros"),api("lotes")]);
    if (versao!==versaoSessao) return;
    if (estadoServidor && JSON.stringify(estado.periodo_anterior)!==JSON.stringify(estadoServidor.periodo_anterior)) $("apuracao").checked=false;
    estadoServidor=estado; conectado(true); atualizarCampos();
    $("modo").textContent={consulta:"Somente consulta",windows:"Executor Windows",simulacao:"Teste simulado"}[estado.modo] || "Servidor";
    $("sessao").textContent=estado.controle_execucao?.estado==="pausada" ? "Execução pausada" : estado.controle_execucao?.estado==="pausa_solicitada" ? "Pausa solicitada" : estado.ocupado ? "Execução em andamento" : "Disponível";
    if (estado.modo==="simulacao") aviso("Modo simulado: este teste não opera o Domínio nem gera documentos fiscais.");
    else if (!estado.execucao_habilitada) aviso("O servidor está em consulta. O responsável precisa habilitar o executor para receber comandos.");
    const localizada=pedidoPendente && tarefas.find(t=>t.pedido.request_id===pedidoPendente.request_id);
    if (localizada) {selecionarTarefa(localizada.id); pedidoPendente=null;}
    if (!tarefaAtual && tarefas.length) selecionarTarefa(tarefas[0].id);
    exibirHistorico(tarefas);
    exibirRotinas(rotinas);
    await painelLotes.atualizar(cadastros,lotes);
    if (versao!==versaoSessao) return;
    atualizarBotao(); await acompanhar(); await exibirCaptura();
  } catch (erro) {if (versao===versaoSessao) {estadoServidor=null; conectado(false); atualizarBotao(); aviso(`Conexão ou resultado indisponível. ${erro.message}`);}}
  finally {atualizando=false;}
}
$("form-login").addEventListener("submit",async(e)=>{
  e.preventDefault(); if (conectando) return;
  conectando=true; chave=$("chave").value.trim(); const versao=++versaoSessao;
  try {const estado=await api("estado"); if (versao!==versaoSessao) return;
    const funcoes=await api("capacidades"); if (versao!==versaoSessao) return;
    estadoServidor=estado; catalogo=funcoes; $("capacidade").replaceChildren();
    for (const item of catalogo) {const opcao=document.createElement("option"); opcao.value=item.id; opcao.textContent=item.nome; $("capacidade").append(opcao);}
    $("chave").value=""; $("login").hidden=true; $("conteudo").hidden=false; $("sair").hidden=false;
    atualizarCampos(); aviso(""); await atualizar();
  } catch (erro) {if (versao===versaoSessao) {chave=""; aviso(erro.message);}}
  finally {conectando=false;}
});
function adicionarPasso() {
  if ($("rotina-passos").children.length>=80) return;
  const linha=document.createElement("div"); linha.className="passo-rotina";
  const tipo=document.createElement("select"); tipo.setAttribute("aria-label","Tipo de ação");
  for (const [valor,nome] of [["clicar","Clicar no texto"],["hover","Passar o mouse no texto"],["tecla","Pressionar tecla"],["digitar","Preencher parâmetro"]]) {const opcao=document.createElement("option"); opcao.value=valor; opcao.textContent=nome; tipo.append(opcao);}
  const valores=document.createElement("div"); valores.className="valor-passo";
  function atualizarValor() {
    valores.replaceChildren();
    if (["clicar","hover"].includes(tipo.value)) {const campo=document.createElement("input"); campo.placeholder="Texto exato na tela"; campo.required=true; campo.maxLength=100; campo.setAttribute("aria-label","Texto a localizar"); valores.append(campo);}
    else {const campo=document.createElement("select"); campo.setAttribute("aria-label","Valor do passo");
      const opcoes=tipo.value==="tecla" ? ["tab","enter","esc","home","end","up","down","left","right","f8"].map(v=>[v,v]) : [["inicio","Data inicial"],["fim","Data final"],["competencia","Mês e ano"],["empresa_codigo","Código da empresa"]];
      for (const [valor,nome] of opcoes) {const opcao=document.createElement("option"); opcao.value=valor; opcao.textContent=nome; campo.append(opcao);} valores.append(campo);
    }
  }
  tipo.addEventListener("change",atualizarValor); atualizarValor();
  const remover=document.createElement("button"); remover.type="button"; remover.className="secundario"; remover.textContent="Remover"; remover.addEventListener("click",()=>linha.remove());
  linha.append(tipo,valores,remover); $("rotina-passos").append(linha);
}
function exibirRotinas(rotinas) {
  $("rotinas-configuradas").replaceChildren();
  for (const rotina of rotinas) {const linha=document.createElement("tr"); celula(linha,rotina.nome); celula(linha,rotina.status==="aprovada" ? "Aprovada no gravador" : "Rascunho · precisa de revisão"); celula(linha,String(rotina.quantidade_passos)); $("rotinas-configuradas").append(linha);}
}
$("adicionar-passo").addEventListener("click",adicionarPasso); adicionarPasso();
$("form-rotina").addEventListener("submit",async e=>{
  e.preventDefault(); if (configurando || !chave || !estadoServidor || !navigator.onLine || !$("form-rotina").reportValidity()) return;
  const passos=[...$("rotina-passos").children].map(linha=>({tipo:linha.querySelector("select").value,valor:linha.querySelector(".valor-passo input,.valor-passo select").value}));
  if (!passos.length) {$("rotina-aviso").textContent="Adicione pelo menos um passo."; return;}
  const versao=versaoSessao; configurando=true; $("salvar-rotina").disabled=true;
  try {const rotina=await api("rotinas",{method:"POST",body:JSON.stringify({nome:$("rotina-nome").value,passos})});
    if (versao!==versaoSessao) return;
    $("rotina-aviso").textContent=`${rotina.nome}: rascunho salvo. Revise e teste no fluxo do gravador antes de aprovar.`;
    await atualizar();
  } catch (erro) {if (versao===versaoSessao) $("rotina-aviso").textContent=erro.message;}
  finally {configurando=false; $("salvar-rotina").disabled=false; atualizarLogin();}
});
$("capacidade").addEventListener("change",atualizarCampos); $("sair").addEventListener("click",()=>{desconectar(); aviso("");});
for (const nome of ["capacidade","empresa","inicio","fim","competencia"]) $(nome).addEventListener("input",()=>{$("apuracao").checked=false; atualizarCampos();});
$("form-tarefa").addEventListener("submit",async(e)=>{
  e.preventDefault(); if (enviando || !estadoServidor || !estadoServidor.execucao_habilitada || estadoServidor.ocupado) return;
  const periodo=periodoSelecionado(); if (!periodo || !$("form-tarefa").reportValidity()) return;
  const dados={capacidade:$("capacidade").value,empresa_codigo:$("empresa").value.trim(),...periodo,apuracao_confirmada:$("apuracao").checked};
  if (!pedidoPendente || JSON.stringify(dados)!==JSON.stringify(pedidoPendente.dados)) pedidoPendente={dados,request_id:crypto.randomUUID()};
  enviando=true; atualizarBotao(); const versao=versaoSessao;
  try {const tarefa=await api("tarefas",{method:"POST",body:JSON.stringify({...dados,request_id:pedidoPendente.request_id})});
    if (versao!==versaoSessao) return;
    selecionarTarefa(tarefa.id); pedidoPendente=null; $("apuracao").checked=false;
    for (const nome of ["competencia","inicio","fim"]) $(nome).value="";
    aviso(""); await acompanhar(); await atualizar();}
  catch (erro) {if (versao===versaoSessao) aviso(`${erro.message} Confira o histórico antes de repetir; uma nova tentativa com os mesmos campos reutiliza o identificador.`);}
  finally {enviando=false; atualizarBotao();}
});
$("pausar").addEventListener("click",async()=>{
  const controle=estadoServidor?.controle_execucao, identificador=tarefaAtual, versao=versaoSessao;
  if (controlando || !navigator.onLine || controle?.tarefa_id!==identificador) return;
  const acao=controle.estado==="pausada" ? "continuar" : "pausar";
  controlando=true; atualizarControle();
  try {const resposta=await api(`tarefas/${identificador}/${acao}`,{method:"POST"});
    if (versao!==versaoSessao || identificador!==tarefaAtual) return;
    if (estadoServidor) estadoServidor.controle_execucao=resposta; atualizarControle(); await atualizar();
  } catch (erro) {if (versao===versaoSessao) aviso(erro.message);}
  finally {controlando=false; atualizarControle();}
});
$("baixar").addEventListener("click",async()=>{
  const versao=versaoSessao, identificador=tarefaAtual;
  try {const resposta=await fetch(`/api/tarefas/${identificador}/arquivo`,{headers:{"Authorization":`Bearer ${chave}`},cache:"no-store"}); if (!resposta.ok) throw new Error("Arquivo indisponível.");
    const disposicao=resposta.headers.get("Content-Disposition") || "", unicode=disposicao.match(/filename\*=utf-8''([^;]+)/i), normal=disposicao.match(/filename="([^"]+)"/i);
    const nome=unicode ? decodeURIComponent(unicode[1]) : normal ? normal[1] : `documento_${tarefaAtual}.pdf`;
    const arquivo=await resposta.blob(); if (versao!==versaoSessao || identificador!==tarefaAtual) return;
    const url=URL.createObjectURL(arquivo), link=document.createElement("a"); link.href=url; link.download=nome; link.click(); URL.revokeObjectURL(url);
  } catch (erro) {if (versao===versaoSessao) aviso(erro.message);}
});
let instalacao=null;
window.addEventListener("beforeinstallprompt",(e)=>{e.preventDefault(); instalacao=e; $("instalar").hidden=false;});
$("instalar").addEventListener("click",async()=>{if (!instalacao) return; await instalacao.prompt(); await instalacao.userChoice; instalacao=null; $("instalar").hidden=true;});
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(()=>{});
window.addEventListener("offline",()=>{estadoServidor=null; conectado(false); atualizarBotao(); aviso("Sem conexão. Nenhuma nova tarefa será enviada; o resultado será consultado quando a conexão voltar.");});
setInterval(atualizar,2000);
