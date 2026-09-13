"""Menu, lobby, selection and result views; each is mounted by its own Level."""
import pyray as rl
from .ui_base import Canvas, INK, MUTED, PAPER, TEAL, RED, LINE, WHITE
from .catalog import HEROES, CELLS, BACTERIA, can_select, unlocked
from .network import connect, disconnect


class MenuScreen(Canvas):
    def __init__(self):
        super().__init__()
        self.ip = "127.0.0.1"
        self.name = "Worker 1146"
        self.error = ""
        self.show_help = False

    def open_session(self, host):
        try:
            connect(self.game, "0.0.0.0" if host else self.ip.strip(), 25765, host, self.name)
        except (OSError, ValueError):
            self.error = "Nao foi possivel abrir a sala. Confira o IP e a porta 25765."
            return
        self.game.new_game("lobby")

    def loop(self):
        super().loop()
        if self.focus:
            text = getattr(self, self.focus)
            char = rl.get_char_pressed()
            while char:
                if 32 <= char < 127 and len(text) < (48 if self.focus == "ip" else 20):
                    text += chr(char)
                char = rl.get_char_pressed()
            if rl.is_key_pressed(rl.KeyboardKey.KEY_BACKSPACE):
                text = text[:-1]
            setattr(self, self.focus, text)

    def field(self, field, label, x, y, w):
        self.text(label, x, y-19, 11, MUTED)
        self.panel(x, y, w, 43, WHITE)
        self.panel(x, y+42, w, 2, TEAL if self.focus == field else LINE)
        self.text(getattr(self, field)+("|" if self.focus == field else ""), x+12, y+10, 18)
        self.controls.append((self.rect(x, y, w, 43), lambda: setattr(self, "focus", field)))

    def render(self):
        self.chrome("01 / CENTRAL DE OPERACOES")
        self.panel(685, 96, 551, 552, (219, 230, 213))
        self.circle(960, 368, 229, (203, 220, 201))
        self.circle(960, 368, 187, (229, 236, 220))
        for i in range(8):
            self.line(706, 151+i*64, 505, (210, 224, 206))
        self.text("IMMUNE RESPONSE UNIT", 716, 116, 12, TEAL)
        self.text("1146", 1043, 546, 73, (176, 202, 179))
        self.portrait("neutrophil", 724, 139, 439, 487)
        self.panel(704, 575, 217, 55, INK)
        self.text("NEUTROPHIL", 721, 584, 21, WHITE)
        self.text("PRIMEIRA LINHA DE DEFESA", 722, 611, 10, (180, 207, 189))
        self.text("O CORPO E O SEU CAMPO DE BATALHA.", 47, 118, 13, TEAL)
        self.text("CELLS", 40, 145, 99)
        self.text("AT WORK", 40, 239, 99)
        self.panel(47, 347, 5, 47, RED)
        self.text("Uma invasao. Seis combatentes.", 65, 345, 23)
        self.text("Defenda o organismo ou estabeleca a infeccao.", 65, 376, 18, MUTED)
        self.field("name", "SEU NOME", 47, 434, 216)
        self.field("ip", "IP DO SERVIDOR", 280, 434, 342)
        self.button("CRIAR SALA  >", 47, 498, 280, lambda: self.open_session(True), True, h=55)
        self.button("ENTRAR NA REDE", 343, 498, 279, lambda: self.open_session(False), h=55)
        self.text("3v3 EM REDE", 47, 579, 13, TEAL)
        self.text("8 HEROIS", 244, 579, 13, TEAL)
        self.text("1 CORPO VIVO", 437, 579, 13, TEAL)
        self.text(self.error or "ABRASION  /  Breach > Identification > Colonization", 47, 617, 13, RED if self.error else MUTED)


def leave(game):
    disconnect(game)
    game.new_game("menu")


class LobbyScreen(Canvas):
    def render(self):
        self.chrome("02 / PREPARACAO DA EQUIPE")
        net = self.game.session
        self.text("OPERACAO ABRASION", 45, 110, 42)
        self.text("Escolha sua funcao. Prepare a equipe. Proteja ou invada.", 47, 164, 18, MUTED)
        self.text(f"{sum(not p['bot'] for p in net.roster.values())} / 6 CONECTADOS", 1018, 121, 19, TEAL)
        for team, x, title, subtitle, accent in [(CELLS, 46, "DEFESA IMUNE", "CONTER / IDENTIFICAR / ELIMINAR", TEAL),
                                                (BACTERIA, 658, "INVASAO BACTERIANA", "INVADIR / ADERIR / COLONIZAR", RED)]:
            self.panel(x, 214, 576, 324, WHITE)
            self.panel(x, 214, 576, 5, accent)
            self.text(title, x+22, 236, 27)
            self.text(subtitle, x+23, 273, 12, MUTED)
            for row, slot in enumerate(range(3) if team == CELLS else range(3, 6)):
                y = 310+row*70
                p = net.roster.get(slot)
                self.line(x+20, y+57, 534)
                self.text(f"0{slot%3+1}", x+24, y+7, 21, accent)
                if p:
                    self.text(p["name"]+("  / VOCE" if slot == net.local_slot else ""), x+79, y, 21)
                    self.text(HEROES[p["hero"]].name, x+80, y+29, 12, MUTED)
                else:
                    self.text("Aguardando combatente...", x+79, y+13, 19, MUTED)
        self.button("ESCOLHER HEROI", 46, 564, 246, lambda: self.game.new_game("selection"), True, net.local_slot is not None)
        self.button("SAIR", 309, 564, 103, lambda: leave(self.game))
        if net.is_server:
            self.button("TREINO + BOTS", 676, 564, 250, lambda: net.start(True))
            self.button("INICIAR 3v3  >", 944, 564, 290, lambda: net.start(False), True, len(net.roster) == 6)
        else:
            self.text("O anfitriao inicia a partida.", 901, 580, 20, MUTED)
        self.text(net.error or f"REDE LOCAL  /  TCP 25765  /  {'Compartilhe o IPv4 deste computador com a equipe.' if net.is_server else net.ip}", 48, 636, 14, RED if net.error else MUTED)


class SelectionScreen(Canvas):
    def render(self):
        self.chrome("03 / SELECAO DE PERSONAGEM")
        net = self.game.session
        local = net.roster.get(net.local_slot)
        self.text("CADA CELULA TEM UMA FUNCAO.", 46, 109, 38)
        self.text("Selecione para ocupar uma vaga. Especialistas imunes sao liberados durante a partida.", 48, 164, 17, MUTED)
        for i, (key, hero) in enumerate(HEROES.items()):
            col, row = i % 4, i // 4
            x, y = 46+col*300, 218+row*184
            selected = local and local["hero"] == key
            available = can_select(key, hero.team, net.roster, exclude=net.local_slot)
            if local and local["team"] != hero.team:
                available = available and sum(p["team"] == hero.team for p in net.roster.values()) < 3
            self.panel(x, y, 279, 165, (218, 231, 211) if selected else WHITE)
            self.panel(x, y, 4, 165, TEAL if hero.team == CELLS else RED)
            self.text(hero.name, x+17, y+14, 19)
            self.text(hero.role, x+18, y+42, 10, MUTED)
            self.text(f"{hero.health} HP  /  {hero.magazine} MUN.", x+18, y+71, 13)
            self.portrait(key, x+172, y+44, 99, 118)
            label = "SELECIONADO" if selected else "BLOQUEADO" if not unlocked(key, 0, False) else "OCUPADO" if not available else "SELECIONAR"
            self.button(label, x+16, y+115, 164, lambda h=key: net.choose(h), selected, available or bool(selected), h=35)
        self.button("< VOLTAR A EQUIPE", 46, 610, 280, lambda: self.game.new_game("lobby"), True)
        self.text("B Cell: 50% antigeno  /  Killer T: tecido infectado", 701, 625, 15, MUTED)


class ResultScreen(Canvas):
    def render(self):
        self.chrome("05 / RELATORIO DA OPERACAO")
        net = self.game.session
        data = net.latest or {"state": {}, "actors": {}}
        state = data["state"]
        winner = state.get("winner", CELLS)
        self.text("INFECCAO CONTIDA" if winner == CELLS else "INFECCAO ESTABELECIDA", 46, 115, 48, TEAL if winner == CELLS else RED)
        self.text("O resultado foi determinado pelos objetivos de Abrasion.", 49, 178, 20, MUTED)
        self.text(f"TEMPO  {int(state.get('elapsed', 0))//60:02}:{int(state.get('elapsed', 0))%60:02}       ANTIGENO  {int(state.get('recognition', 0))}%       STRESS  {int(state.get('stress', 0))}%", 49, 223, 17)
        for i, (slot, player) in enumerate(sorted(net.roster.items())):
            y = 289+i*45
            a = data["actors"].get(slot, {})
            self.panel(46, y, 1188, 39, WHITE)
            self.text(player["name"], 64, y+8, 19)
            self.text(HEROES[player["hero"]].name, 400, y+9, 17)
            self.text("CELULAS" if player["team"] == CELLS else "BACTERIAS", 800, y+10, 14, TEAL if player["team"] == CELLS else RED)
            self.text(f"{a.get('kills', 0)} K   /   {a.get('deaths', 0)} D", 1080, y+8, 18)
        self.button("VOLTAR AO MENU", 46, 600, 300, lambda: leave(self.game), True)
