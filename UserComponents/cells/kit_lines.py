"""Textos do lobby: nome/função de cada herói e as falas em 1ª pessoa do mini tutorial.

As falas resumem ``catalog.KIT`` na voz do personagem (com acentos, pois os menus usam
fontes com Latin-1). Ao mudar um kit em ``catalog.py``, atualize a fala aqui também.
Cada fala: (nome da habilidade, frase).
"""
from .catalog import KIT

NAMES = {
    "neutrophil": ("Neutrófilo", "Combatente"),
    "macrophage": ("Macrófago", "Tanque / Antígenos"),
    "b_cell": ("B Cell", "Precisão / Suporte"),
    "killer_t": ("Killer T", "Investida"),
    "pneumococcus": ("Pneumococcus", "Tanque frontal"),
    "staphylococcus": ("Staphylococcus", "Colonização"),
    "pseudomonas": ("Pseudomonas", "Controle de área"),
    "streptococcus": ("Streptococcus", "Flanqueador"),
}

LINES = {
    "neutrophil": dict(
        passive=("Receptor", "Inimigos abaixo de 50% de vida aparecem pra mim através das paredes."),
        lmb=("Fuzil", "Rajada automática e precisa."),
        rmb=("Faca", "Golpe corpo a corpo. Pelas costas, eu corto em dobro!"),
        q=("Avanço cortante", "Atravesso cortando quem estiver no caminho. Eliminou? Recarrega na hora!"),
        e=("Rede NET", "Prendo o alvo no lugar por 1,5 s."),
        f=("Quimiotaxia", "Revelo todos os inimigos, acelero a equipe e ganho 3 avanços seguidos!"),
        tip="Persiga alvos marcados pelo B Cell: eles recebem +15% de dano."),
    "macrophage": dict(
        passive=("Fagocitose", "Eliminar alguém de perto me cura 25% da vida."),
        lmb=("Escopeta", "Chumbo de curto alcance."),
        rmb=("Engolir", "Segura o botão que eu devoro os tiros da frente! Barra de 3 s, sem atirar."),
        q=("Pseudópode", "Lanço um gancho e puxo o inimigo até mim. Vem cá!"),
        e=("Machadada", "Um golpe pesado em arco que empurra todo mundo."),
        f=("Banquete", "6 s de Engolir infinito e em dobro; o que eu como vira escudo dos aliados. F de novo: cuspo tudo!"),
        tip="Fique na frente: cada tiro engolido carrega o Banquete."),
    "b_cell": dict(
        passive=("Opsonização", "Meus acertos marcam o alvo: ele recebe +15% de dano."),
        lmb=("Rifle", "Tiro preciso de alto dano."),
        rmb=("Mira", "Zoom com dano extra."),
        q=("Plasmócito", "Posiciono uma torreta (160 HP, 15 m) que atira e marca. Clique pra fixar."),
        e=("Granada de anticorpos", "Explode em área, causa dano e marca todo mundo."),
        f=("Chuva de anticorpos", "Vista aérea: faço chover anticorpos e guio a chuva com WASD, sentadinho no chão!"),
        tip="Sua marca alimenta a equipe: o Killer T ganha +20% contra marcados."),
    "killer_t": dict(
        passive=("Licença para matar", "+20% de dano contra alvos marcados."),
        lmb=("Rajada", "Três tiros por gatilho."),
        rmb=("Soco carregado", "Segura pra carregar, solta pra socar e arremessar!"),
        q=("Salto de impacto", "Salto num piscar de olhos até onde eu mirar e esmago tudo no círculo de pouso!"),
        e=("Perforina", "Injeto perforina: o alvo sofre dano extra depois de 3 s."),
        f=("Ativação total", "8 s em 3ª pessoa: mais rápido, mais dano e roubo de vida!"),
        tip="Combine Perforina com a marca do B Cell para derrubar tanques."),
    "pneumococcus": dict(
        passive=("Cápsula", "Tenho um escudo próprio que se regenera fora de combate."),
        lmb=("Disparo", "Glóbulos de média distância."),
        rmb=("Barreira", "Segura: levanto uma barreira frontal de 600 HP. Sem atirar."),
        q=("Investida", "Avanço e prendo o primeiro inimigo que eu atingir."),
        e=("Cápsula compartilhada", "+100 de escudo pra mim e pro aliado mais próximo."),
        f=("Pneumonia", "Uma nuvem me segue: dá dano, cega inimigos e para as plaquetas!"),
        tip="Fique à frente das plaquetas com a barreira levantada."),
    "staphylococcus": dict(
        passive=("Cacho", "Regenero vida perto de colônias."),
        lmb=("Disparo", "Glóbulos de média distância."),
        rmb=("Projétil aderente", "Gruda no alvo e deixa ele lento. Não adianta correr!"),
        q=("Coagulase", "Ergo uma parede de coágulo (6 m, 5 s). Clique pra fixar."),
        e=("Toxina", "Corto toda a cura e regeneração do alvo por 5 s."),
        f=("Abscesso", "Um domo que bloqueia os tiros de fora e protege quem está dentro!"),
        tip="Use a parede para fechar o caminho das plaquetas."),
    "pseudomonas": dict(
        passive=("Corrosão", "+30% de dano contra alvos abaixo de 50% de vida."),
        lmb=("Disparo", "Ácido que deixa poças."),
        rmb=("Granada ácida", "Segura pra ver o arco, solta pra lançar."),
        q=("Biofilme", "Deslizo deixando um rastro que acelera aliados e prende inimigos."),
        e=("Flagelo", "Gancho: me puxo até a superfície mirada."),
        f=("Quorum sensing", "A equipe toda ganha +20% de dano e velocidade, com biofilme maduro ao redor!"),
        tip="Corrosão finaliza: mire em quem já está ferido."),
    "streptococcus": dict(
        passive=("Hemólise", "Dano dobrado contra hemácias."),
        lmb=("Metralhadora", "Rajada rápida de curto alcance."),
        rmb=("Golpe", "Corte rápido, devastador em hemácias."),
        q=("Arrancada", "Avanço na direção da mira. Tenho 2 cargas!"),
        e=("Corrente", "Lanço a corrente: me puxo até o alvo e deixo ele lento."),
        f=("Divisão binária", "Crio 2 clones que correm e atiram!"),
        tip="Flanqueie: cace hemácias longe da equipe inimiga."),
}


def name(hero):
    return NAMES.get(hero, (hero, ""))[0]


def role(hero):
    return NAMES.get(hero, ("", ""))[1]


def line(hero, slot):
    """(nome, fala) da habilidade; cai no texto do ``KIT`` se faltar a fala."""
    entry = LINES.get(hero, {}).get(slot)
    if entry:
        return entry
    return KIT.get(hero, {}).get(slot, ("", ""))


def tip(hero):
    return LINES.get(hero, {}).get("tip") or KIT.get(hero, {}).get("tip", "")
