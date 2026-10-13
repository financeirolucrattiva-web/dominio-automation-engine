"use strict";
const painelLotes=(()=>{
  let cadastro={empresas:[],regimes:[]}, cadastroTexto="", sequencia=[], plano=null, loteAtual=null, detalhe=null, ocupado=false, pedidoLote=null;
  const selecionadas=new Set();
  let planoPiloto=null, pedidoPiloto=null, versaoPiloto=0, consultaPiloto="";
  const nomeRotina=id=>(cadastro.rotinas || catalogo).find(r=>r.id===id)?.nome || "Rotina indisponível";
  const statusRotinas={integrada:"Integrada · revalidar no Windows",pendente_configuracao:"Pendente de configuração",rascunho:"Rascunho · revisar e testar",aguardando_validacao:"Enviada para validação · execução bloqueada"};
  function pastaInformada() {
    let valor=$("empresa-pasta").value.trim().replace(/^"(.*)"$/, "$1").replaceAll("\\","/").replace(/\/$/,"");
    const raiz=(cadastro.destino_livros?.raiz || "").replaceAll("\\","/").replace(/\/$/,"");
    if (/^[a-zA-Z]:/.test(valor) || valor.startsWith("/")) {
      if (!raiz || !valor.toLowerCase().startsWith(raiz.toLowerCase()+"/")) return null;
      valor=valor.slice(raiz.length+1);
    }
    return valor;
  }
  function opcoes(select, itens, inicial) {
    const valor=select.value; select.replaceChildren();
    if (inicial!==null) {const o=document.createElement("option"); o.value=""; o.textContent=inicial; select.append(o);}
    for (const item of itens) {const o=document.createElement("option"); o.value=item.id; o.textContent=item.nome; select.append(o);}
    if ([...select.options].some(o=>o.value===valor)) select.value=valor;
  }
  function invalidar() {plano=null; pedidoLote=null; $("lote-revisao").hidden=true; $("lote-apuracao").checked=false; controles();}
  function controles() {
    const online=!!chave && !!estadoServidor && navigator.onLine;
    for (const id of ["salvar-regime","salvar-empresa","regime-adicionar","lote-planejar","cadastrar-rotina","empresa-ver-destino","empresa-testar-pasta"]) $(id).disabled=!online || ocupado;
    for (const b of $("rotinas-cadastradas").querySelectorAll("button")) b.disabled=!online || ocupado || b.dataset.aguardando==="true";
    for (const select of $("lote-empresas").querySelectorAll("select")) select.disabled=!online || ocupado;
    $("lote-executar").disabled=!online || ocupado || !plano || !estadoServidor?.execucao_habilitada || estadoServidor?.ocupado;
    $("piloto-revisar").disabled=!online || ocupado;
    $("piloto-executar").disabled=!online || ocupado || !planoPiloto || !estadoServidor?.execucao_habilitada || estadoServidor?.ocupado ||
      (planoPiloto.quantidade_pendencias>0 && !$("piloto-parcial").checked);
    atualizarLimitePeriodo("piloto-competencia",estadoServidor?.periodo_anterior.inicio.slice(0,7) || "");
    $("lote-apuracao").disabled=!plano;
    const competencia=$("lote-tipo-periodo").value==="competencia";
    $("lote-campo-competencia").hidden=!competencia; $("lote-campo-datas").hidden=competencia; $("lote-competencia").disabled=!competencia;
    const mesMaximo=estadoServidor?.periodo_anterior.inicio.slice(0,7) || "";
    for (const id of ["lote-competencia","empresa-competencia"]) atualizarLimitePeriodo(id,mesMaximo);
    for (const id of ["lote-inicio","lote-fim"]) {$(id).disabled=competencia; atualizarLimitePeriodo(id,estadoServidor?.periodo_anterior.fim || "");}
    const ativo=detalhe?.tarefas?.some(t=>t.id===estadoServidor?.controle_execucao?.tarefa_id);
    const estado=estadoServidor?.controle_execucao?.estado;
    $("lote-pausar").hidden=!ativo; $("lote-pausar").disabled=!online || ocupado || estado==="pausa_solicitada";
    $("lote-pausar").textContent=estado==="pausada" ? "Continuar execução" : estado==="pausa_solicitada" ? "Pausa solicitada…" : "Pausar execução";
    $("lote-cancelar").hidden=!detalhe || !["pendente","executando"].includes(detalhe.status);
    $("lote-cancelar").disabled=!online || ocupado;
    $("lote-diagnostico").hidden=!detalhe; $("lote-diagnostico").disabled=!online || ocupado;
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
      editar.addEventListener("click",()=>{$("config-empresas").open=true; $("empresa-codigo").value=empresa.codigo; $("empresa-nome").value=empresa.nome; $("empresa-regime").value=empresa.regime_id; $("empresa-pasta").value=empresa.pasta_relativa || ""; $("empresa-subpasta").value=empresa.subpasta_livros || ""; $("empresa-destino").textContent=""; $("empresa-nome").focus();}); celula(linha,"").append(editar);
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
  $("form-empresa").addEventListener("submit",async e=>{e.preventDefault(); if (!$("form-empresa").reportValidity()) return; if (await salvarCadastro("empresas",{codigo:$("empresa-codigo").value,nome:$("empresa-nome").value,regime_id:$("empresa-regime").value,pasta_relativa:$("empresa-pasta").value,subpasta_livros:$("empresa-subpasta").value})) {$("empresa-destino").textContent="Empresa salva. Use Editar na lista e confira o destino antes do teste."; $("form-empresa").reset(); $("empresa-raiz").value=cadastro.destino_livros?.raiz || "";}});
  async function conferirDestino(testar) {
    const codigo=$("empresa-codigo").value, competencia=$("empresa-competencia").value;
    if (!codigo || !competencia) {$("empresa-destino").textContent="Use Editar numa empresa salva e informe a competência para conferir o destino."; return;}
    if (ocupado || !chave || !estadoServidor) return;
    const empresa=cadastro.empresas.find(e=>e.codigo===String(Number(codigo)));
    if (!empresa || empresa.pasta_relativa!==pastaInformada() || empresa.subpasta_livros!==$("empresa-subpasta").value.replaceAll("\\","/").trim() || empresa.regime_id!==$("empresa-regime").value || empresa.nome!==$("empresa-nome").value.trim()) {$("empresa-destino").textContent="Salve as alterações da empresa e use Editar antes de conferir o destino."; return;}
    ocupado=true; controles(); const versao=versaoSessao;
    try {const destino=await api(`empresas/${encodeURIComponent(codigo)}/destino-livros`,{method:"POST",body:JSON.stringify({competencia,testar_gravacao:testar})});
      if (versao!==versaoSessao) return;
      $("empresa-destino").textContent=`${destino.gravacao_confirmada ? "Gravação confirmada. Teste de pasta concluído; não emite relatório fiscal." : "Destino previsto; nenhuma pasta ou arquivo foi criado."} Pasta local: ${destino.caminho_local}. ${destino.caminho_dominio ? "No Domínio: "+destino.caminho_dominio+". " : ""}Arquivos previstos: ${destino.arquivos_previstos.join(", ")}.`;
    } catch (erro) {if (versao===versaoSessao) $("empresa-destino").textContent=erro.message;}
    finally {ocupado=false; controles();}
  }
  $("empresa-ver-destino").addEventListener("click",()=>conferirDestino(false));
  $("empresa-testar-pasta").addEventListener("click",()=>conferirDestino(true));
  $("form-cadastro-rotina").addEventListener("submit",async e=>{e.preventDefault(); if (!$("form-cadastro-rotina").reportValidity()) return; if (await salvarCadastro("rotinas/cadastros",{nome:$("cadastro-rotina-nome").value})) $("form-cadastro-rotina").reset();});
  function selecaoPiloto() {
    const mes=$("piloto-competencia").value, codigo=$("piloto-empresa").value;
    if (!codigo || !/^[0-9]{4}-(0[1-9]|1[0-2])$/.test(mes) || mes.startsWith("0000")) return null;
    const ultimo=new Date(`${mes}-01T00:00:00Z`); ultimo.setUTCMonth(ultimo.getUTCMonth()+1); ultimo.setUTCDate(0);
    return {empresas:[codigo],inicio:`${mes}-01`,fim:ultimo.toISOString().slice(0,10)};
  }
  function invalidarPiloto() {
    versaoPiloto++; planoPiloto=null; pedidoPiloto=null; consultaPiloto="";
    $("piloto-apuracao").checked=false; $("piloto-parcial").checked=false; $("piloto-rotinas").replaceChildren();
    $("piloto-resumo").textContent="Escolha empresa e competência para conferir a sequência."; controles();
  }
  async function revisarPiloto() {
    const dados=selecaoPiloto(); if (!dados || !chave || !estadoServidor || !navigator.onLine) return;
    const assinatura=JSON.stringify(dados)+cadastroTexto;
    if (consultaPiloto===assinatura) return;
    consultaPiloto=assinatura; const versao=++versaoPiloto, sessao=versaoSessao;
    planoPiloto=null; $("piloto-resumo").textContent="Conferindo sequência da empresa…"; controles();
    try {
      const revisao=await api("piloto-presumido/planejar",{method:"POST",body:JSON.stringify(dados)});
      if (sessao!==versaoSessao || versao!==versaoPiloto) return;
      planoPiloto=revisao; $("piloto-rotinas").replaceChildren();
      const empresa=revisao.empresas[0], pendencias=revisao.pendencias;
      for (const id of empresa.sequencia_cadastrada) {
        const pendente=pendencias.find(p=>p.rotina_id===id), li=document.createElement("li");
        li.textContent=nomeRotina(id)+(pendente ? " · Pendente de integração; não será executada" : " · Disponível para teste supervisionado");
        $("piloto-rotinas").append(li);
      }
      $("piloto-resumo").textContent=`${empresa.codigo} · ${empresa.nome} · ${dados.inicio} a ${dados.fim}. ${revisao.quantidade_rotinas} rotinas disponíveis; ${revisao.quantidade_pendencias} pendentes.`+
        (revisao.quantidade_pendencias ? " A sequência inteira ainda não está liberada. Para testar as disponíveis, marque a opção de teste parcial." : " Será executada toda a sequência cadastrada no regime.");
    } catch (erro) {if (sessao===versaoSessao && versao===versaoPiloto) {consultaPiloto=""; $("piloto-resumo").textContent=erro.message;}}
    finally {controles();}
  }
  for (const id of ["piloto-empresa","piloto-competencia"]) $(id).addEventListener("input",()=>{invalidarPiloto(); revisarPiloto();});
  $("piloto-parcial").addEventListener("change",controles);
  $("piloto-revisar").addEventListener("click",()=>{invalidarPiloto(); revisarPiloto();});
  $("form-piloto").addEventListener("submit",async e=>{
    e.preventDefault(); if (!$("form-piloto").reportValidity()) return;
    const dados=selecaoPiloto();
    if (!dados || !planoPiloto || ocupado || !estadoServidor?.execucao_habilitada || estadoServidor?.ocupado) return;
    if (planoPiloto.quantidade_pendencias && !$("piloto-parcial").checked) return;
    const envio={...dados,plano_hash:planoPiloto.hash,apuracao_confirmada:true};
    const assinatura=JSON.stringify(envio);
    if (!pedidoPiloto || pedidoPiloto.assinatura!==assinatura) pedidoPiloto={assinatura,request_id:crypto.randomUUID()};
    ocupado=true; controles(); const sessao=versaoSessao;
    try {
      const lote=await api("piloto-presumido",{method:"POST",body:JSON.stringify({...envio,request_id:pedidoPiloto.request_id})});
      if (sessao!==versaoSessao) return;
      aceitarLote(lote.id); $("piloto-apuracao").checked=false;
      $("piloto-aviso").textContent=`Teste recebido. ${lote.plano.quantidade_pendencias ? "Teste parcial: as pendentes não serão executadas. " : ""}Acompanhe os resultados abaixo.`;
      $("config-lotes").open=true; await atualizar(); $("lote-resultado").scrollIntoView({behavior:"smooth",block:"center"});
    } catch (erro) {if (sessao===versaoSessao) $("piloto-aviso").textContent=erro.message+" Confira o histórico antes de repetir; o mesmo pedido não repete a emissão.";}
    finally {ocupado=false; controles();}
  });
  $("lote-filtro").addEventListener("change",()=>{selecionadas.clear(); invalidar(); exibirEmpresas();});
  $("lote-selecionar").addEventListener("click",()=>{for (const e of cadastro.empresas.filter(e=>!$("lote-filtro").value || e.regime_id===$("lote-filtro").value)) selecionadas.add(e.codigo); invalidar(); exibirEmpresas();});
  $("lote-limpar").addEventListener("click",()=>{selecionadas.clear(); invalidar(); exibirEmpresas();});
  for (const id of ["lote-tipo-periodo","lote-competencia","lote-inicio","lote-fim","lote-piloto"]) $(id).addEventListener("input",invalidar);
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
    invalidar(); ocupado=true; controles(); const versao=versaoSessao, cadastroAntes=cadastroTexto, piloto=$("lote-piloto").checked;
    try {const revisao=await api(piloto ? "piloto-presumido/planejar" : "lotes/planejar",{method:"POST",body:JSON.stringify(dados)});
      if (versao!==versaoSessao || cadastroAntes!==cadastroTexto || piloto!==$("lote-piloto").checked || JSON.stringify(dados)!==JSON.stringify(selecao())) return;
      plano=revisao; $("lote-plano").replaceChildren(); let ordem=0;
      for (const empresa of plano.empresas) for (const rotina of empresa.rotinas) {const linha=document.createElement("tr"); celula(linha,String(++ordem)); celula(linha,`${empresa.codigo} · ${empresa.nome}`); celula(linha,nomeRotina(rotina)); $("lote-plano").append(linha);}
      const data=d=>d.split("-").reverse().join("/"); $("lote-plano-resumo").textContent=`${plano.empresas.length} empresa(s) · ${plano.quantidade_rotinas} rotina(s) · ${data(plano.inicio)} a ${data(plano.fim)}`;
      if (plano.quantidade_pendencias) {
        $("lote-plano-resumo").textContent+=` · Teste parcial: ${plano.quantidade_pendencias} pendências não serão executadas.`;
        for (const pendente of plano.pendencias) {const linha=document.createElement("tr"); celula(linha,"—"); celula(linha,pendente.empresa_codigo); celula(linha,pendente.nome+" · Não será executada"); $("lote-plano").append(linha);}
      }
      $("lote-revisao").hidden=false; $("lote-aviso").textContent="Confira a sequência antes de iniciar.";
    } catch (erro) {if (versao===versaoSessao) $("lote-aviso").textContent=erro.message;}
    finally {ocupado=false; controles();}
  });
  $("form-lote").addEventListener("submit",async e=>{
    e.preventDefault(); if (!plano || ocupado || !estadoServidor?.execucao_habilitada || estadoServidor.ocupado || !$("form-lote").reportValidity()) return;
    const dados={...selecao(),apuracao_confirmada:$("lote-apuracao").checked,plano_hash:plano.hash};
    if (!pedidoLote || JSON.stringify(dados)!==JSON.stringify(pedidoLote.dados)) pedidoLote={dados,request_id:crypto.randomUUID()};
    ocupado=true; controles(); const versao=versaoSessao;
    try {const lote=await api(plano.piloto_presumido ? "piloto-presumido" : "lotes",{method:"POST",body:JSON.stringify({...dados,request_id:pedidoLote.request_id})});
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
  $("lote-diagnostico").addEventListener("click",async()=>{
    if (!detalhe || !chave || !estadoServidor || ocupado || !navigator.onLine) return;
    const sessao=versaoSessao,id=loteAtual;
    try {
      const relatorio=await api(`lotes/${id}/diagnostico`);
      if (sessao!==versaoSessao || id!==loteAtual) return;
      const url=URL.createObjectURL(new Blob([JSON.stringify(relatorio,null,2)],{type:"application/json"}));
      try {const link=document.createElement("a"); link.href=url; link.download=`diagnostico_presumido_${id}.json`; link.click();}
      finally {URL.revokeObjectURL(url);}
    } catch (erro) {if (sessao===versaoSessao) $("lote-aviso").textContent=erro.message;}
  });
  async function atualizarPainel(novoCadastro,lotes) {
    const raiz=novoCadastro.destino_livros?.raiz || "";
    if ($("empresa-raiz").value!==raiz) $("empresa-raiz").value=raiz;
    const texto=JSON.stringify(novoCadastro);
    if (texto!==cadastroTexto) {
      invalidar(); invalidarPiloto(); cadastro=novoCadastro; cadastroTexto=texto;
      opcoes($("regime-editar"),cadastro.regimes,"Criar regime"); opcoes($("empresa-regime"),cadastro.regimes,"Escolha o regime"); opcoes($("lote-filtro"),cadastro.regimes,"Todos os regimes");
      opcoes($("regime-rotina"),cadastro.rotinas || catalogo,null); exibirEmpresas(); exibirSequencia(); exibirRotinasCadastradas();
      const presumidos=new Set(cadastro.regimes.filter(r=>r.nome.trim().toLowerCase()==="lucro presumido").map(r=>r.id));
      opcoes($("piloto-empresa"),cadastro.empresas.filter(e=>presumidos.has(e.regime_id)).map(e=>({id:e.codigo,nome:`${e.codigo} · ${e.nome}`})),"Escolha uma empresa cadastrada");
      revisarPiloto();
    }
    const encontrado=pedidoLote && lotes.find(l=>l.request_id===pedidoLote.request_id);
    if (encontrado) {aceitarLote(encontrado.id); invalidar();}
    if (!loteAtual && lotes.length) loteAtual=lotes[0].id;
    opcoes($("lote-historico"),lotes.map(l=>({id:l.id,nome:`${new Date(l.criado).toLocaleString("pt-BR")} · ${nomesStatus[l.status] || "Não confirmado"} · ${l.plano.quantidade_rotinas} rotinas`})),"Nenhum lote"); $("lote-historico").value=loteAtual || "";
    if (loteAtual) {
      const versao=versaoSessao, id=loteAtual, resultado=await api(`lotes/${id}`);
      if (versao!==versaoSessao || id!==loteAtual) return; detalhe=resultado;
      const feitas=detalhe.tarefas.filter(t=>t.status==="concluida").length;
      const motivo={rotina_nao_concluida:"A recuperação até a tela azul não foi confirmada; as próximas foram interrompidas.",rotinas_com_falhas:"As rotinas com falha permanecem no histórico. Após recuperar a tela azul, a sequência continua.",rotinas_nao_integradas:"As rotinas em configuração não foram executadas; o teste completo ainda está pendente.",lote_cancelado:"Interrupção solicitada. A ação atual termina em um ponto seguro.",servidor_reiniciado:"O servidor reiniciou. O lote não foi repetido.",reinicio_solicitado:"Reinício do ciclo solicitado."}[detalhe.motivo] || "";
      $("lote-resultado").textContent=`${nomesStatus[detalhe.status] || "Não confirmado"} · ${feitas}/${detalhe.tarefas.length} rotinas concluídas. ${motivo}`;
      if (detalhe.plano.quantidade_pendencias) $("lote-resultado").textContent+=` ${detalhe.plano.quantidade_pendencias} pendências não executadas.`;
      $("lote-tarefas").replaceChildren();
      for (const tarefa of detalhe.tarefas) {
        const empresa=detalhe.plano.empresas.find(e=>e.codigo===tarefa.pedido.empresa_codigo), linha=document.createElement("tr");
        celula(linha,`${empresa.codigo} · ${empresa.nome}`); celula(linha,nomeRotina(tarefa.pedido.capacidade)+(tarefa.modo==="simulacao" ? " (simulada)" : ""));
        celula(linha,(nomesStatus[tarefa.status] || "Não confirmado")+(tarefa.motivo && motivos[tarefa.motivo] ? " · "+motivos[tarefa.motivo] : "")).className=tarefa.status;
        const b=document.createElement("button"); b.type="button"; b.className="secundario"; b.textContent="Ver etapas"; b.addEventListener("click",()=>{selecionarTarefa(tarefa.id); acompanhar().catch(erro=>aviso(erro.message)); $("resultado").scrollIntoView({behavior:"smooth",block:"center"});}); celula(linha,"").append(b); $("lote-tarefas").append(linha);
      }
      for (const pendente of detalhe.plano.pendencias || []) {
        const empresa=detalhe.plano.empresas.find(e=>e.codigo===pendente.empresa_codigo), linha=document.createElement("tr");
        celula(linha,`${empresa.codigo} · ${empresa.nome}`); celula(linha,pendente.nome); celula(linha,"Não executada · integração pendente"); celula(linha,"Confira o formulário dos livros, se for essa rotina."); $("lote-tarefas").append(linha);
      }
    }
    controles();
  }
  function limpar() {
    cadastro={empresas:[],regimes:[]}; cadastroTexto=""; sequencia=[]; plano=null; pedidoLote=null; loteAtual=null; detalhe=null; selecionadas.clear(); $("empresa-raiz").value="";
    for (const id of ["form-regime","form-empresa","form-lote","form-piloto"]) $(id).reset();
    invalidarPiloto(); $("piloto-empresa").replaceChildren(); $("piloto-aviso").textContent="";
    for (const id of ["lote-empresas","lote-plano","lote-tarefas","regime-sequencia"]) $(id).replaceChildren();
    for (const [id,nome] of [["regime-editar","Criar regime"],["empresa-regime","Escolha o regime"],["lote-filtro","Todos os regimes"],["lote-historico","Nenhum lote"]]) opcoes($(id),[],nome);
    $("regime-rotina").replaceChildren(); $("cadastro-aviso").textContent=$("lote-aviso").textContent=$("empresa-destino").textContent=""; $("lote-resultado").textContent="Aguardando seleção"; invalidar();
  }
  return {atualizar:atualizarPainel,controles,limpar};
})();
