"use strict";
const painelLotes=(()=>{
  let cadastro={empresas:[],regimes:[]}, cadastroTexto="", sequencia=[], plano=null, loteAtual=null, detalhe=null, ocupado=false, pedidoLote=null;
  const selecionadas=new Set();
  const nomeRotina=id=>(cadastro.rotinas || catalogo).find(r=>r.id===id)?.nome || "Rotina indisponível";
  const statusRotinas={integrada:"Integrada · revalidar no Windows",pendente_configuracao:"Pendente de configuração",rascunho:"Rascunho · revisar e testar",aguardando_validacao:"Enviada para validação · execução bloqueada"};
  function opcoes(select, itens, inicial) {
    const valor=select.value; select.replaceChildren();
    if (inicial!==null) {const o=document.createElement("option"); o.value=""; o.textContent=inicial; select.append(o);}
    for (const item of itens) {const o=document.createElement("option"); o.value=item.id; o.textContent=item.nome; select.append(o);}
    if ([...select.options].some(o=>o.value===valor)) select.value=valor;
  }
  function invalidar() {plano=null; pedidoLote=null; $("lote-revisao").hidden=true; $("lote-apuracao").checked=false; controles();}
  function controles() {
    const online=!!chave && !!estadoServidor && navigator.onLine;
    for (const id of ["salvar-regime","salvar-empresa","regime-adicionar","lote-planejar","cadastrar-rotina"]) $(id).disabled=!online || ocupado;
    for (const b of $("rotinas-cadastradas").querySelectorAll("button")) b.disabled=!online || ocupado || b.dataset.aguardando==="true";
    for (const select of $("lote-empresas").querySelectorAll("select")) select.disabled=!online || ocupado;
    $("lote-executar").disabled=!online || ocupado || !plano || !estadoServidor?.execucao_habilitada || estadoServidor?.ocupado;
    $("lote-apuracao").disabled=!plano;
    const competencia=$("lote-tipo-periodo").value==="competencia";
    $("lote-campo-competencia").hidden=!competencia; $("lote-campo-datas").hidden=competencia; $("lote-competencia").disabled=!competencia;
    $("lote-competencia").max=estadoServidor?.periodo_anterior.inicio.slice(0,7) || "";
    for (const id of ["lote-inicio","lote-fim"]) {$(id).disabled=competencia; $(id).max=estadoServidor?.periodo_anterior.fim || "";}
    const ativo=detalhe?.tarefas?.some(t=>t.id===estadoServidor?.controle_execucao?.tarefa_id);
    const estado=estadoServidor?.controle_execucao?.estado;
    $("lote-pausar").hidden=!ativo; $("lote-pausar").disabled=!online || ocupado || estado==="pausa_solicitada";
    $("lote-pausar").textContent=estado==="pausada" ? "Continuar execução" : estado==="pausa_solicitada" ? "Pausa solicitada…" : "Pausar execução";
    $("lote-cancelar").hidden=!detalhe || !["pendente","executando"].includes(detalhe.status);
    $("lote-cancelar").disabled=!online || ocupado;
  }
  function exibirSequencia() {
    $("regime-sequencia").replaceChildren();
    sequencia.forEach((id,indice)=>{
      const li=document.createElement("li"); li.append(document.createTextNode(nomeRotina(id)));
      const botoes=document.createElement("div"); botoes.className="controle";
      for (const [texto,delta] of [["Subir",-1],["Descer",1],["Remover",0]]) {
        const b=document.createElement("button"); b.type="button"; b.className="secundario"; b.textContent=texto;
        b.disabled=delta!==0 && (indice+delta<0 || indice+delta>=sequencia.length);
        b.addEventListener("click",()=>{if (delta===0) sequencia.splice(indice,1); else [sequencia[indice],sequencia[indice+delta]]=[sequencia[indice+delta],sequencia[indice]]; exibirSequencia();}); botoes.append(b);
      }
      li.append(botoes); $("regime-sequencia").append(li);
      const rotina=cadastro.rotinas?.find(r=>r.id===id);
      if (rotina) {const status=document.createElement("small"); status.className="discreto"; status.textContent=statusRotinas[rotina.status] || "Não configurada"; li.append(status);}
    });
  }
  function exibirRotinasCadastradas() {
    $("rotinas-cadastradas").replaceChildren();
    for (const rotina of cadastro.rotinas || []) {
      const linha=document.createElement("tr"); celula(linha,rotina.nome);
      celula(linha,cadastro.regimes.filter(r=>r.rotinas.includes(rotina.id)).map(r=>r.nome).join(", ") || "Ainda sem vínculo");
      celula(linha,statusRotinas[rotina.status] || "Não configurada"); const acoes=celula(linha,"");
      if (rotina.status!=="integrada") {
        const b=document.createElement("button"); b.type="button"; b.className="secundario"; b.textContent="Configurar";
        b.addEventListener("click",()=>configurarRotinaCadastrada(rotina.id)); acoes.append(b);
        if (rotina.quantidade_passos>0) {const validar=document.createElement("button"); validar.type="button"; validar.className="secundario";
          validar.textContent=rotina.status==="aguardando_validacao" ? "Enviada para validação" : "Enviar para validação";
          validar.dataset.aguardando=String(rotina.status==="aguardando_validacao");
          validar.addEventListener("click",()=>salvarCadastro(`rotinas/cadastros/${rotina.id}/validacao`,{})); acoes.append(validar);}
      }
      $("rotinas-cadastradas").append(linha);
    }
  }
  function exibirEmpresas() {
    $("lote-empresas").replaceChildren();
    const visiveis=cadastro.empresas.filter(e=>!$("lote-filtro").value || e.regime_id===$("lote-filtro").value);
    $("lote-vazio").hidden=!!visiveis.length;
    for (const empresa of visiveis) {
      const linha=document.createElement("tr"), check=document.createElement("input"); check.type="checkbox"; check.checked=selecionadas.has(empresa.codigo);
      check.setAttribute("aria-label",`Selecionar ${empresa.nome}`); check.dataset.codigo=empresa.codigo;
      check.addEventListener("change",()=>{if (check.checked) selecionadas.add(empresa.codigo); else selecionadas.delete(empresa.codigo); invalidar();});
      celula(linha,"").append(check); celula(linha,`${empresa.codigo} · ${empresa.nome}`);
      const regime=document.createElement("select"); regime.setAttribute("aria-label",`Regime de ${empresa.nome}`); opcoes(regime,cadastro.regimes,null); regime.value=empresa.regime_id; regime.disabled=ocupado || !chave || !estadoServidor;
      regime.addEventListener("change",async()=>{if (ocupado) {regime.value=empresa.regime_id; return;} regime.disabled=true; invalidar(); if (!await salvarCadastro("empresas",{...empresa,regime_id:regime.value})) regime.value=empresa.regime_id; controles();}); celula(linha,"").append(regime);
      const editar=document.createElement("button"); editar.type="button"; editar.className="secundario"; editar.textContent="Editar";
      editar.addEventListener("click",()=>{$("config-empresas").open=true; $("empresa-codigo").value=empresa.codigo; $("empresa-nome").value=empresa.nome; $("empresa-regime").value=empresa.regime_id; $("empresa-nome").focus();}); celula(linha,"").append(editar);
      $("lote-empresas").append(linha);
    }
  }
  async function salvarCadastro(caminho,dados) {
    if (ocupado || !chave || !estadoServidor || !navigator.onLine) return false;
    ocupado=true; controles(); const versao=versaoSessao;
    try {await api(caminho,{method:"POST",body:JSON.stringify(dados)}); if (versao!==versaoSessao) return false;
      invalidar(); $("cadastro-aviso").textContent="Cadastro salvo no servidor. Novos lotes usarão esta configuração."; await atualizar(); return true;
    } catch (erro) {if (versao===versaoSessao) {$("cadastro-aviso").textContent=erro.message; cadastroTexto="";} return false;}
    finally {ocupado=false; controles();}
  }
  $("regime-editar").addEventListener("change",()=>{const r=cadastro.regimes.find(r=>r.id===$("regime-editar").value); $("regime-nome").value=r?.nome || ""; sequencia=[...(r?.rotinas || [])]; exibirSequencia();});
  $("regime-adicionar").addEventListener("click",()=>{const id=$("regime-rotina").value; if (id && !sequencia.includes(id)) {sequencia.push(id); exibirSequencia();}});
  $("form-regime").addEventListener("submit",async e=>{e.preventDefault(); if (!$("form-regime").reportValidity()) return; await salvarCadastro("regimes",{id:$("regime-editar").value || null,nome:$("regime-nome").value,rotinas:sequencia});});
  $("form-empresa").addEventListener("submit",async e=>{e.preventDefault(); if (!$("form-empresa").reportValidity()) return; if (await salvarCadastro("empresas",{codigo:$("empresa-codigo").value,nome:$("empresa-nome").value,regime_id:$("empresa-regime").value})) $("form-empresa").reset();});
  $("form-cadastro-rotina").addEventListener("submit",async e=>{e.preventDefault(); if (!$("form-cadastro-rotina").reportValidity()) return; if (await salvarCadastro("rotinas/cadastros",{nome:$("cadastro-rotina-nome").value})) $("form-cadastro-rotina").reset();});
  $("lote-filtro").addEventListener("change",()=>{selecionadas.clear(); invalidar(); exibirEmpresas();});
  $("lote-selecionar").addEventListener("click",()=>{for (const e of cadastro.empresas.filter(e=>!$("lote-filtro").value || e.regime_id===$("lote-filtro").value)) selecionadas.add(e.codigo); invalidar(); exibirEmpresas();});
  $("lote-limpar").addEventListener("click",()=>{selecionadas.clear(); invalidar(); exibirEmpresas();});
  for (const id of ["lote-tipo-periodo","lote-competencia","lote-inicio","lote-fim"]) $(id).addEventListener("input",invalidar);
  function selecao() {
    let inicio=$("lote-inicio").value, fim=$("lote-fim").value;
    if ($("lote-tipo-periodo").value==="competencia") {
      const mes=$("lote-competencia").value;
      if (!/^[0-9]{4}-(0[1-9]|1[0-2])$/.test(mes) || mes.startsWith("0000")) return null;
      const ultimo=new Date(`${mes}-01T00:00:00Z`); ultimo.setUTCMonth(ultimo.getUTCMonth()+1); ultimo.setUTCDate(0);
      inicio=`${mes}-01`; fim=ultimo.toISOString().slice(0,10);
    }
    if (!inicio || !fim || !selecionadas.size) return null;
    return {empresas:cadastro.empresas.filter(e=>selecionadas.has(e.codigo)).map(e=>e.codigo),inicio,fim};
  }
  $("lote-planejar").addEventListener("click",async()=>{
    const dados=selecao(); if (!dados) {$("lote-aviso").textContent="Selecione empresas e informe a competência ou as duas datas."; return;}
    if (ocupado || !chave || !estadoServidor) return;
    invalidar(); ocupado=true; controles(); const versao=versaoSessao, cadastroAntes=cadastroTexto;
    try {const revisao=await api("lotes/planejar",{method:"POST",body:JSON.stringify(dados)});
      if (versao!==versaoSessao || cadastroAntes!==cadastroTexto || JSON.stringify(dados)!==JSON.stringify(selecao())) return;
      plano=revisao; $("lote-plano").replaceChildren(); let ordem=0;
      for (const empresa of plano.empresas) for (const rotina of empresa.rotinas) {const linha=document.createElement("tr"); celula(linha,String(++ordem)); celula(linha,`${empresa.codigo} · ${empresa.nome}`); celula(linha,nomeRotina(rotina)); $("lote-plano").append(linha);}
      const data=d=>d.split("-").reverse().join("/"); $("lote-plano-resumo").textContent=`${plano.empresas.length} empresa(s) · ${plano.quantidade_rotinas} rotina(s) · ${data(plano.inicio)} a ${data(plano.fim)}`;
      $("lote-revisao").hidden=false; $("lote-aviso").textContent="Confira a sequência antes de iniciar.";
    } catch (erro) {if (versao===versaoSessao) $("lote-aviso").textContent=erro.message;}
    finally {ocupado=false; controles();}
  });
  $("form-lote").addEventListener("submit",async e=>{
    e.preventDefault(); if (!plano || ocupado || !estadoServidor?.execucao_habilitada || estadoServidor.ocupado || !$("form-lote").reportValidity()) return;
    const dados={...selecao(),apuracao_confirmada:$("lote-apuracao").checked,plano_hash:plano.hash};
    if (!pedidoLote || JSON.stringify(dados)!==JSON.stringify(pedidoLote.dados)) pedidoLote={dados,request_id:crypto.randomUUID()};
    ocupado=true; controles(); const versao=versaoSessao;
    try {const lote=await api("lotes",{method:"POST",body:JSON.stringify({...dados,request_id:pedidoLote.request_id})});
      if (versao!==versaoSessao) return; aceitarLote(lote.id); invalidar(); for (const id of ["lote-competencia","lote-inicio","lote-fim"]) $(id).value=""; await atualizar();
    } catch (erro) {if (versao===versaoSessao) $("lote-aviso").textContent=`${erro.message} Confira o histórico antes de repetir; o mesmo plano reutiliza o identificador.`;}
    finally {ocupado=false; controles();}
  });
  function aceitarLote(id) {loteAtual=id; detalhe=null; $("lote-aviso").textContent="Lote recebido. Acompanhe os resultados por empresa abaixo.";}
  $("lote-historico").addEventListener("change",()=>{loteAtual=$("lote-historico").value; detalhe=null; atualizar();});
  async function controlarLote(acao) {
    if (ocupado || !estadoServidor || !chave || !loteAtual) return;
    const tarefa=estadoServidor.controle_execucao?.tarefa_id;
    if (acao!=="cancelar" && !detalhe?.tarefas.some(t=>t.id===tarefa)) return;
    ocupado=true; controles(); const versao=versaoSessao;
    try {await api(acao==="cancelar" ? `lotes/${loteAtual}/cancelar` : `tarefas/${tarefa}/${acao}`,{method:"POST"}); if (versao!==versaoSessao) return; await atualizar();}
    catch (erro) {if (versao===versaoSessao) $("lote-aviso").textContent=erro.message;}
    finally {ocupado=false; controles();}
  }
  $("lote-cancelar").addEventListener("click",()=>controlarLote("cancelar"));
  $("lote-pausar").addEventListener("click",()=>controlarLote(estadoServidor?.controle_execucao?.estado==="pausada" ? "continuar" : "pausar"));
  async function atualizarPainel(novoCadastro,lotes) {
    const texto=JSON.stringify(novoCadastro);
    if (texto!==cadastroTexto) {
      invalidar(); cadastro=novoCadastro; cadastroTexto=texto;
      opcoes($("regime-editar"),cadastro.regimes,"Criar regime"); opcoes($("empresa-regime"),cadastro.regimes,"Escolha o regime"); opcoes($("lote-filtro"),cadastro.regimes,"Todos os regimes");
      opcoes($("regime-rotina"),cadastro.rotinas || catalogo,null); exibirEmpresas(); exibirSequencia(); exibirRotinasCadastradas();
    }
    const encontrado=pedidoLote && lotes.find(l=>l.request_id===pedidoLote.request_id);
    if (encontrado) {aceitarLote(encontrado.id); invalidar();}
    if (!loteAtual && lotes.length) loteAtual=lotes[0].id;
    opcoes($("lote-historico"),lotes.map(l=>({id:l.id,nome:`${new Date(l.criado).toLocaleString("pt-BR")} · ${nomesStatus[l.status] || "Não confirmado"} · ${l.plano.quantidade_rotinas} rotinas`})),"Nenhum lote"); $("lote-historico").value=loteAtual || "";
    if (loteAtual) {
      const versao=versaoSessao, id=loteAtual, resultado=await api(`lotes/${id}`);
      if (versao!==versaoSessao || id!==loteAtual) return; detalhe=resultado;
      const feitas=detalhe.tarefas.filter(t=>t.status==="concluida").length;
      const motivo={rotina_nao_concluida:"A recuperação até a tela azul não foi confirmada; as próximas foram interrompidas.",rotinas_com_falhas:"As rotinas com falha permanecem no histórico. Após recuperar a tela azul, a sequência continua.",lote_cancelado:"Interrupção solicitada. A ação atual termina em um ponto seguro.",servidor_reiniciado:"O servidor reiniciou. O lote não foi repetido.",reinicio_solicitado:"Reinício do ciclo solicitado."}[detalhe.motivo] || "";
      $("lote-resultado").textContent=`${nomesStatus[detalhe.status] || "Não confirmado"} · ${feitas}/${detalhe.tarefas.length} rotinas concluídas. ${motivo}`;
      $("lote-tarefas").replaceChildren();
      for (const tarefa of detalhe.tarefas) {
        const empresa=detalhe.plano.empresas.find(e=>e.codigo===tarefa.pedido.empresa_codigo), linha=document.createElement("tr");
        celula(linha,`${empresa.codigo} · ${empresa.nome}`); celula(linha,nomeRotina(tarefa.pedido.capacidade)+(tarefa.modo==="simulacao" ? " (simulada)" : "")); celula(linha,nomesStatus[tarefa.status] || "Não confirmado").className=tarefa.status;
        const b=document.createElement("button"); b.type="button"; b.className="secundario"; b.textContent="Ver etapas"; b.addEventListener("click",()=>{selecionarTarefa(tarefa.id); acompanhar().catch(erro=>aviso(erro.message)); $("resultado").scrollIntoView({behavior:"smooth",block:"center"});}); celula(linha,"").append(b); $("lote-tarefas").append(linha);
      }
    }
    controles();
  }
  function limpar() {
    cadastro={empresas:[],regimes:[]}; cadastroTexto=""; sequencia=[]; plano=null; pedidoLote=null; loteAtual=null; detalhe=null; selecionadas.clear();
    for (const id of ["form-regime","form-empresa","form-lote"]) $(id).reset();
    for (const id of ["lote-empresas","lote-plano","lote-tarefas","regime-sequencia"]) $(id).replaceChildren();
    for (const [id,nome] of [["regime-editar","Criar regime"],["empresa-regime","Escolha o regime"],["lote-filtro","Todos os regimes"],["lote-historico","Nenhum lote"]]) opcoes($(id),[],nome);
    $("regime-rotina").replaceChildren(); $("cadastro-aviso").textContent=$("lote-aviso").textContent=""; $("lote-resultado").textContent="Aguardando seleção"; invalidar();
  }
  return {atualizar:atualizarPainel,controles,limpar};
})();
