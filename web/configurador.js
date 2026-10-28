"use strict";
// Configurador visual de rotinas: marca-se o alvo em um print da tela do Domínio (nada de texto exato por OCR).
// Usa $, api e chave de app.js. O navegador só envia retângulos; o servidor recorta os modelos de imagem.
const configuradorVisual=(()=>{
  const nomesTipo={clicar:"Clicar",duplo_clique:"Duplo clique",hover:"Passar o mouse",esperar_imagem:"Esperar imagem",se_aparecer:"Se aparecer",se_aparecer_clicar:"Se aparecer → clicar",se_aparecer_tecla:"Se aparecer → tecla",tecla:"Tecla",digitar:"Digitar",esperar_segundos:"Esperar"};
  const teclas=["tab","enter","esc","home","end","up","down","left","right","pageup","pagedown","f8"];
  const tiposAlvo=["clicar","duplo_clique","hover","esperar_imagem"];
  const nomesParametro={inicio:"Data inicial (AAAA-MM-DD)",fim:"Data final (AAAA-MM-DD)",competencia:"Competência (AAAA-MM)",empresa_codigo:"Código da empresa"};
  let passos=[], rotinaId=null, captura=null, imagem=null, modo="clicar", arrasto=null, ocupado=false, condicaoPendente=null;
  const el=id=>$(id);

  // A política de segurança da página só aceita imagens "self" e "data:", então o blob vira data URL.
  const blobParaDados=blob=>new Promise((resolve,reject)=>{const leitor=new FileReader(); leitor.onload=()=>resolve(leitor.result); leitor.onerror=reject; leitor.readAsDataURL(blob);});
  function mensagem(texto, erro=false) {const p=el("cv-aviso"); p.textContent=texto; p.classList.toggle("erro",erro);}
  async function pedido(caminho, opcoes={}) {
    const resposta=await fetch(`/api/${caminho}`, {...opcoes, headers:{"Authorization":`Bearer ${chave}`, ...(opcoes.corpo?{"Content-Type":"application/json"}:{})}, cache:"no-store"});
    if (!resposta.ok) {const dados=await resposta.json().catch(()=>({})); throw new Error(dados.detail || `Erro ${resposta.status}`);}
    return resposta;
  }
  const json=async(caminho, opcoes={})=>(await pedido(caminho, opcoes)).json();
  const enviar=(metodo, caminho, corpo)=>json(caminho, {method:metodo, body:corpo===undefined?undefined:JSON.stringify(corpo), corpo:corpo!==undefined});

  async function aguardar(finais, limite=300000) {
    const fim=Date.now()+limite;
    while (Date.now()<fim) {
      const estado=await json("estado"), login=estado.login;
      if (finais.includes(login.estado)) return login;
      await new Promise(r=>setTimeout(r,1000));
    }
    throw new Error("O servidor não respondeu a tempo. Confira o painel do servidor.");
  }

  function desenhar() {
    const tela=el("cv-tela"); if (!imagem) return;
    const contexto=tela.getContext("2d");
    contexto.drawImage(imagem,0,0);
    contexto.lineWidth=2;
    for (const passo of passos) {
      if (passo.captura_id!==captura || passo.largura===undefined) continue;
      contexto.strokeStyle="#168066"; contexto.strokeRect(passo.x,passo.y,passo.largura,passo.altura);
    }
    if (condicaoPendente) {contexto.strokeStyle="#e67e22"; contexto.strokeRect(condicaoPendente.x,condicaoPendente.y,condicaoPendente.largura,condicaoPendente.altura);}
    if (arrasto) {contexto.strokeStyle="#c0392b"; contexto.strokeRect(arrasto.x,arrasto.y,arrasto.largura,arrasto.altura);}
  }
  function ponto(evento) {
    const tela=el("cv-tela"), caixa=tela.getBoundingClientRect();
    const limitar=(v,max)=>Math.max(0,Math.min(max,v));
    return {x:limitar(Math.round((evento.clientX-caixa.left)*tela.width/caixa.width),tela.width), y:limitar(Math.round((evento.clientY-caixa.top)*tela.height/caixa.height),tela.height)};
  }
  function retangulo(a,b) {return {x:Math.min(a.x,b.x), y:Math.min(a.y,b.y), largura:Math.abs(a.x-b.x), altura:Math.abs(a.y-b.y)};}

  function recortePrevia(r) {
    const c=document.createElement("canvas"); c.width=Math.min(r.largura,240); c.height=Math.round(r.altura*c.width/r.largura);
    c.getContext("2d").drawImage(imagem,r.x,r.y,r.largura,r.altura,0,0,c.width,c.height); return c.toDataURL("image/png");
  }
  function marcarSeAparecer(r) {
    const tecla=modo==="se_aparecer_tecla";
    if (!condicaoPendente) {
      if (r.largura<16 || r.altura<16) {mensagem("Arraste sobre a TELA que pode aparecer (pelo menos 16x16 pixels): um pedaço característico dela, como o título e o texto.", true); return;}
      condicaoPendente={...r, previa:recortePrevia(r)};
      if (!tecla) {mensagem("Tela marcada (laranja). Agora arraste sobre o botão a clicar, nesta mesma imagem (ex.: o OK)."); desenhar(); return;}
    }
    const base={tipo:"se_aparecer", rotulo:"", captura_id:captura, x:condicaoPendente.x, y:condicaoPendente.y, largura:condicaoPendente.largura, altura:condicaoPendente.altura, previa:condicaoPendente.previa, espera:10, obrigatorio:false};
    if (tecla) base.resposta={tipo:"tecla", tecla:"enter"};
    else {
      if (r.largura<8 || r.altura<8) {mensagem("Arraste um retângulo de pelo menos 8x8 pixels sobre o botão.", true); return;}
      base.resposta={tipo:"clicar", x:r.x, y:r.y, largura:r.largura, altura:r.altura, rotulo:""}; base.previaAlvo=recortePrevia(r);
    }
    condicaoPendente=null; passos.push(base); desenhar();
    mensagem("Condição criada. Descreva a tela e o botão na lista de passos. Por padrão ela é opcional: se não aparecer, a rotina segue."); renderizarPassos();
    const campos=document.querySelectorAll("#cv-passos .rotulo-passo"); campos[campos.length-(tecla?1:2)]?.focus();
  }
  function marcar(r) {
    if (modo.startsWith("se_aparecer")) return marcarSeAparecer(r);
    if (r.largura<8 || r.altura<8) {mensagem("Arraste um retângulo de pelo menos 8x8 pixels sobre o alvo.", true); return;}
    const passo={tipo:modo, rotulo:"", captura_id:captura, ...r, previa:recortePrevia(r)};
    if (modo==="esperar_imagem") passo.segundos=15;
    passos.push(passo); mensagem("Alvo marcado. Descreva-o em poucas palavras na lista de passos."); renderizarPassos();
    const campos=document.querySelectorAll("#cv-passos .rotulo-passo"); campos[campos.length-1]?.focus();
  }

  function renderizarPassos() {
    const lista=el("cv-passos"); lista.replaceChildren();
    passos.forEach((passo,i)=>{
      const item=document.createElement("li"); item.className="passo-visual";
      const titulo=document.createElement("strong"); titulo.textContent=nomesTipo[passo.tipo]||passo.tipo; item.append(titulo);
      if (passo.tipo==="se_aparecer") {
        if (passo.previa) {const m=document.createElement("img"); m.src=passo.previa; m.alt="Tela esperada"; m.className="miniatura"; item.append(m);}
        const rotulo=document.createElement("input"); rotulo.className="rotulo-passo"; rotulo.maxLength=80; rotulo.placeholder="Qual tela é esta? (ex.: aviso Outros dados)"; rotulo.value=passo.rotulo||"";
        rotulo.addEventListener("input",()=>{passo.rotulo=rotulo.value;}); item.append(rotulo);
        if (passo.resposta.tipo==="clicar") {
          item.append(document.createTextNode(" → clicar em "));
          if (passo.previaAlvo) {const m=document.createElement("img"); m.src=passo.previaAlvo; m.alt="Botão"; m.className="miniatura"; item.append(m);}
          const r=document.createElement("input"); r.className="rotulo-passo"; r.maxLength=80; r.placeholder="Qual botão? (ex.: Sim)"; r.value=passo.resposta.rotulo||""; r.addEventListener("input",()=>{passo.resposta.rotulo=r.value;}); item.append(r);
        } else {
          item.append(document.createTextNode(" → tecla "));
          const sel=document.createElement("select"); for (const t of teclas) {const o=document.createElement("option"); o.value=t; o.textContent=t; sel.append(o);} sel.value=passo.resposta.tecla; sel.addEventListener("change",()=>{passo.resposta.tecla=sel.value;}); item.append(sel);
        }
        const obrig=document.createElement("label"); obrig.className="confirmacao"; const caixa=document.createElement("input"); caixa.type="checkbox"; caixa.checked=!!passo.obrigatorio; caixa.addEventListener("change",()=>{passo.obrigatorio=caixa.checked;});
        const texto=document.createElement("span"); texto.textContent="Obrigatória (falha se não aparecer)"; obrig.append(caixa,texto); item.append(obrig);
        const s=document.createElement("input"); s.type="number"; s.min=1; s.max=120; s.value=passo.espera||10; s.className="espera-passo"; s.title="segundos esperando a tela"; s.addEventListener("input",()=>{passo.espera=Number(s.value);}); item.append(document.createTextNode("espera: "),s,document.createTextNode(" s"));
      } else if (tiposAlvo.includes(passo.tipo)) {
        if (passo.previa) {const miniatura=document.createElement("img"); miniatura.src=passo.previa; miniatura.alt="Alvo marcado"; miniatura.className="miniatura"; item.append(miniatura);}
        const rotulo=document.createElement("input"); rotulo.className="rotulo-passo"; rotulo.maxLength=80; rotulo.placeholder="Descreva o alvo (ex.: botão OK do relatório)"; rotulo.value=passo.rotulo||"";
        rotulo.addEventListener("input",()=>{passo.rotulo=rotulo.value;}); item.append(rotulo);
        const campoEspera=(rotuloEspera, chaveEspera, padrao)=>{
          const s=document.createElement("input"); s.type="number"; s.min=1; s.max=120; s.value=passo[chaveEspera]||padrao; s.title=rotuloEspera; s.className="espera-passo"; passo[chaveEspera]=Number(s.value);
          s.addEventListener("input",()=>{passo[chaveEspera]=Number(s.value);}); item.append(document.createTextNode(rotuloEspera+": "),s,document.createTextNode(" s"));
        };
        if (passo.tipo==="esperar_imagem") campoEspera("espera até aparecer","segundos",15);
        else campoEspera("espera pelo alvo","espera",20);
      } else if (passo.tipo==="tecla") {item.append(document.createTextNode(` ${passo.tecla}`));}
      else if (passo.tipo==="digitar") {item.append(document.createTextNode(passo.parametro ? ` parâmetro: ${nomesParametro[passo.parametro]||passo.parametro}` : ` texto fixo: ${passo.texto}`));}
      else if (passo.tipo==="esperar_segundos") {item.append(document.createTextNode(` ${passo.segundos} s`));}
      const acoes=document.createElement("span"); acoes.className="acoes-passo";
      for (const [texto,delta] of [["▲",-1],["▼",1]]) {
        const b=document.createElement("button"); b.type="button"; b.className="secundario"; b.textContent=texto; b.setAttribute("aria-label",delta<0?"Subir passo":"Descer passo");
        b.disabled=i+delta<0 || i+delta>=passos.length; b.addEventListener("click",()=>{[passos[i],passos[i+delta]]=[passos[i+delta],passos[i]]; renderizarPassos();}); acoes.append(b);
      }
      const remover=document.createElement("button"); remover.type="button"; remover.className="secundario"; remover.textContent="Remover"; remover.addEventListener("click",()=>{passos.splice(i,1); renderizarPassos();}); acoes.append(remover);
      item.append(acoes); lista.append(item);
    });
    el("cv-vazio").hidden=passos.length>0; desenhar();
  }

  function corpoRotina() {
    return {nome:el("cv-nome").value, passos:passos.map(p=>{
      const limpo={tipo:p.tipo};
      for (const campo of ["rotulo","captura_id","x","y","largura","altura","segundos","espera","obrigatorio","resposta","tecla","parametro","texto"]) if (p[campo]!==undefined && p[campo]!=="") limpo[campo]=p[campo];
      return limpo;
    })};
  }

  async function capturarTela() {
    if (ocupado) return; ocupado=true; el("cv-capturar").disabled=true; mensagem("Pedindo a captura ao servidor... deixe o Domínio na tela que quer marcar.");
    try {
      await enviar("POST","configurador/captura");
      const login=await aguardar(["captura_configurador_pronta","falha","cancelado"],60000);
      if (login.estado!=="captura_configurador_pronta") throw new Error(login.motivo==="dominio_fora_de_foco" ? "O Domínio não está em foco no servidor. Deixe-o na frente e tente de novo." : "Não consegui capturar a tela. Confira o servidor.");
      const resposta=await pedido("configurador/captura");
      captura=resposta.headers.get("X-Captura-Id"); const blob=await resposta.blob();
      imagem=await createImageBitmap(blob);
      const tela=el("cv-tela"); tela.width=imagem.width; tela.height=imagem.height; desenhar();
      el("cv-area").hidden=false; el("cv-dica").hidden=true; mensagem("Captura pronta. Ação atual: "+nomesTipo[modo]+". Arraste um retângulo sobre o alvo na imagem.");
    } catch (erro) {mensagem(erro.message,true);}
    finally {ocupado=false; el("cv-capturar").disabled=false;}
  }

  function adicionarOutro() {
    const tipo=el("cv-outro-tipo").value, valor=el("cv-outro-valor").value.trim();
    let passo;
    if (tipo.startsWith("alvo_")) {escolherModo(tipo.slice(5)); if (!imagem) {mensagem("Capturando a tela para você marcar o alvo..."); capturarTela();} else mensagem("Arraste um retângulo sobre o alvo na imagem."); return;}
    if (tipo==="tecla") passo={tipo,tecla:valor};
    else if (tipo==="digitar_parametro") passo={tipo:"digitar",parametro:valor};
    else if (tipo==="digitar_texto") passo={tipo:"digitar",texto:valor};
    else passo={tipo:"esperar_segundos",segundos:Number(valor)};
    passos.push(passo); renderizarPassos(); mensagem("Passo adicionado.");
  }
  function escolherModo(novo) {
    modo=novo; condicaoPendente=null; desenhar();
    for (const b of document.querySelectorAll("#cv-modos button")) b.classList.toggle("secundario",b.dataset.modo!==novo);
    if (!imagem) mensagem("Escolha a ação e capture a tela do Domínio (botão acima); depois arraste sobre o alvo.");
  }
  function ajustarCampoOutro() {
    const tipo=el("cv-outro-tipo").value, campo=el("cv-outro-valor"), lista=el("cv-outro-select");
    const opcoes={tecla:["tab","enter","esc","home","end","up","down","left","right","pageup","pagedown","f8"], digitar_parametro:Object.keys(nomesParametro)};
    const semValor=tipo.startsWith("alvo_");
    el("cv-outro-valor").hidden=!!opcoes[tipo]||semValor; lista.hidden=!opcoes[tipo]; lista.replaceChildren();
    for (const o of opcoes[tipo]||[]) {const opcao=document.createElement("option"); opcao.value=o; opcao.textContent=tipo==="digitar_parametro"?nomesParametro[o]:o; lista.append(opcao);}
    campo.placeholder=tipo==="digitar_texto"?"Texto fixo (até 60 letras)":"Segundos (1 a 30)";
  }

  async function salvar() {
    try {
      const corpo=corpoRotina();
      const salva=rotinaId ? await enviar("PUT",`configurador/rotinas/${rotinaId}`,corpo) : await enviar("POST","configurador/rotinas",corpo);
      rotinaId=salva.id; mensagem(`Rotina "${salva.nome}" salva como rascunho. Teste-a com o Domínio na tela de partida.`); await carregarLista(); await abrir(rotinaId,false);
    } catch (erro) {mensagem(erro.message,true);}
  }
  function novo() {passos=[]; rotinaId=null; el("cv-nome").value=""; el("cv-teste").hidden=true; renderizarPassos(); mensagem("Nova rotina. Capture a tela e marque os alvos.");}

  async function abrir(id, avisar=true) {
    try {
      const rotina=await json(`configurador/rotinas/${id}`);
      rotinaId=rotina.id; el("cv-nome").value=rotina.nome;
      passos=await Promise.all(rotina.passos.map(async p=>{
        const passo={...p}; delete passo.indice; delete passo.tem_modelo; delete passo.modelo;
        delete passo.tem_modelo_alvo; delete passo.deslocamento;
        if (p.tem_modelo) {try {const r=await pedido(`configurador/rotinas/${id}/modelo/${p.indice}`); passo.previa=await blobParaDados(await r.blob());} catch {}}
        if (p.tem_modelo_alvo) {try {const r=await pedido(`configurador/rotinas/${id}/modelo/${p.indice}?parte=alvo`); passo.previaAlvo=await blobParaDados(await r.blob());} catch {}}
        return passo;
      }));
      renderizarPassos(); montarTeste(rotina);
      if (avisar) mensagem(`Rotina "${rotina.nome}" aberta (${rotina.status}).`);
    } catch (erro) {mensagem(erro.message,true);}
  }

  function montarTeste(rotina) {
    el("cv-teste").hidden=false; const campos=el("cv-parametros"); campos.replaceChildren();
    for (const nome of rotina.parametros) {
      const rotulo=document.createElement("label"); rotulo.textContent=nomesParametro[nome]||nome;
      const entrada=document.createElement("input"); entrada.dataset.parametro=nome; entrada.required=true; entrada.maxLength=12;
      entrada.placeholder=nome==="empresa_codigo"?"70":nome==="competencia"?"2026-09":"2026-09-01"; rotulo.append(entrada); campos.append(rotulo);
    }
    el("cv-aprovar").disabled=rotina.status!=="testada";
    const resultado=el("cv-resultado"); resultado.replaceChildren();
    const teste=rotina.resultado_teste;
    if (teste) {
      const cabecalho=document.createElement("p"); cabecalho.textContent=`Último teste (${teste.em}): ${teste.ok?"passou":"falhou no passo "+teste.passo_falho}`; resultado.append(cabecalho);
      for (const p of teste.passos||[]) {const linha=document.createElement("div"); linha.className=p.ok?"passo-ok":"passo-falha"; linha.textContent=`${p.ok?"✓":"✗"} Passo ${p.indice}: ${p.detalhe}`; resultado.append(linha);}
    }
  }

  async function testar() {
    if (!rotinaId || ocupado) return; ocupado=true; el("cv-testar").disabled=true;
    const parametros={}; for (const campo of document.querySelectorAll("#cv-parametros input")) parametros[campo.dataset.parametro]=campo.value.trim();
    try {
      mensagem("Testando no servidor. Acompanhe o Domínio e NÃO mexa no mouse nem no teclado do PC do Domínio.");
      await enviar("POST",`configurador/rotinas/${rotinaId}/testar`,{parametros});
      const login=await aguardar(["teste_configurador_ok","falha","cancelado"],600000);
      await abrir(rotinaId,false); await carregarLista();
      mensagem(login.estado==="teste_configurador_ok" ? "Teste passou. Se o resultado no Domínio ficou como esperado, aprove a rotina." : "O teste parou. Veja o passo que falhou abaixo e ajuste a marcação.", login.estado!=="teste_configurador_ok");
    } catch (erro) {mensagem(erro.message,true);}
    finally {ocupado=false; el("cv-testar").disabled=false;}
  }
  async function aprovar() {
    try {await enviar("POST",`configurador/rotinas/${rotinaId}/aprovar`); mensagem("Rotina aprovada."); await abrir(rotinaId,false); await carregarLista();}
    catch (erro) {mensagem(erro.message,true);}
  }

  async function carregarLista() {
    const corpo=el("cv-lista"); corpo.replaceChildren();
    try {
      const rotinas=await json("configurador/rotinas");
      for (const r of rotinas) {
        const linha=document.createElement("tr");
        const nome=document.createElement("td"); nome.textContent=r.nome; linha.append(nome);
        const status=document.createElement("td"); status.textContent=r.status==="aprovada"?"Aprovada":r.status==="testada"?"Testada · falta aprovar":"Rascunho"; linha.append(status);
        const passosCelula=document.createElement("td"); passosCelula.textContent=String(r.quantidade_passos); linha.append(passosCelula);
        const acoes=document.createElement("td");
        const abrirBotao=document.createElement("button"); abrirBotao.type="button"; abrirBotao.className="secundario"; abrirBotao.textContent="Abrir"; abrirBotao.addEventListener("click",()=>abrir(r.id));
        const excluir=document.createElement("button"); excluir.type="button"; excluir.className="secundario"; excluir.textContent="Excluir";
        excluir.addEventListener("click",async()=>{if (!confirm(`Excluir a rotina "${r.nome}"?`)) return; try {await enviar("DELETE",`configurador/rotinas/${r.id}`); if (rotinaId===r.id) novo(); await carregarLista();} catch (erro) {mensagem(erro.message,true);}});
        acoes.append(abrirBotao,document.createTextNode(" "),excluir); linha.append(acoes); corpo.append(linha);
      }
      el("cv-sem-rotinas").hidden=rotinas.length>0;
    } catch (erro) {mensagem(erro.message,true);}
  }

  function iniciar() {
    if (!el("config-visual")) return;
    Object.assign(fasesLogin,{captura_configurador_pronta:"Captura do configurador pronta",teste_configurador_ok:"Teste da rotina concluído"});
    Object.assign(motivosLogin,{configurador_recusado:"O configurador recusou a operação; confira os dados e tente de novo.",teste_configurador_falhou:"O teste parou em um passo; veja o resultado no configurador.",dominio_fora_de_foco:"O Domínio não está em foco no servidor."});
    el("cv-capturar").addEventListener("click",capturarTela);
    for (const botao of document.querySelectorAll("#cv-modos button")) botao.addEventListener("click",()=>escolherModo(botao.dataset.modo));
    const tela=el("cv-tela");
    tela.addEventListener("mousedown",e=>{if (!imagem) return; const p=ponto(e); arrasto={...p,largura:0,altura:0,origem:p};});
    tela.addEventListener("mousemove",e=>{if (!arrasto) return; Object.assign(arrasto,retangulo(arrasto.origem,ponto(e))); desenhar();});
    window.addEventListener("mouseup",e=>{if (!arrasto) return; const r=retangulo(arrasto.origem,ponto(e)); arrasto=null; desenhar(); marcar(r);});
    el("cv-outro-tipo").addEventListener("change",ajustarCampoOutro); ajustarCampoOutro();
    el("cv-adicionar").addEventListener("click",()=>{const t=el("cv-outro-tipo").value; if (t==="tecla"||t==="digitar_parametro") el("cv-outro-valor").value=el("cv-outro-select").value; adicionarOutro();});
    el("cv-salvar").addEventListener("click",salvar); el("cv-novo").addEventListener("click",novo);
    el("cv-testar").addEventListener("click",testar); el("cv-aprovar").addEventListener("click",aprovar);
    el("config-visual").addEventListener("toggle",()=>{if (el("config-visual").open) carregarLista();});
    renderizarPassos();
  }
  iniciar();
  return {passos:()=>passos, definirImagem:(i,c)=>{imagem=i; captura=c;}};
})();
