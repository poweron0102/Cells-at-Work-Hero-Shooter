# Falas dos personagens

Clipes de voz recortados dos episódios de *Cells at Work!* (*Hataraku Saibou*, temporada 1),
com a voz isolada da trilha e dos efeitos pelo Demucs. `ja/` usa o áudio original japonês e
`en/` a dublagem em inglês. O conteúdo pertence aos detentores dos direitos do anime
(Akane Shimizu/Kodansha, Aniplex, David Production; dublagem: Crunchyroll/Funimation) e é usado
aqui apenas neste protótipo de fã, sem fins comerciais.

- Manifesto (episódio, tempos, textos, ajustes): [`scripts/voice_clips.json`](../../../scripts/voice_clips.json)
- Geração: [`scripts/build_voices.py`](../../../scripts/build_voices.py) (instruções no topo do arquivo;
  esta página sai de `build_voices.py --sources`)
- Uso no jogo: `UserComponents/cells/voice.py` e `audio.py`; idioma em `saves/config.json`
  (`{"voice_language": "en"}`) ou `CELLS_VOICE=en`. Padrão: `ja`.

O falante de cada trecho foi conferido pelos quadros do vídeo no momento da fala. As legendas
seguem o áudio japonês; na dublagem, o trecho foi localizado transcrevendo a mesma cena (Whisper),
e os clipes finais dos dois idiomas foram transcritos de novo para conferir o conteúdo.

| Arquivo | Evento | Ep. | JA (tempo · legenda) | EN (tempo · fala) |
| --- | --- | --- | --- | --- |
| `b_cell/e_1.ogg` | habilidade E | S01E05 | 09:25 · Eat this! | 09:21 · You and your buddies are history! |
| `b_cell/kill_1.ogg` | eliminação | S01E05 | 09:21 · See ya later! | 09:19 · Say goodbye! |
| `b_cell/q_1.ogg` | habilidade Q | S01E03 | 17:15 · This puppy should make light work of them. | 17:15 · Never fear the artillery's here! We'll put them down in no time at all! |
| `b_cell/spawn_1.ogg` | entrar em campo | S01E05 | 08:50 · Leave this to me, fellas! / I've got your back! | 08:49 · Stand back and leave this to me! I've got the cure right here! |
| `b_cell/spawn_2.ogg` | entrar em campo | S01E03 | 17:00 · Sorry for the wait. | 16:59 · Sorry it took so long, |
| `b_cell/ult_1.ogg` | especial (F) | S01E03 | 17:01 · B cell, here! / I've come with antibodies! | 17:01 · I've been a little busy whipping up some antibodies! |
| `b_cell/ult_2.ogg` | especial (F) | S01E05 | — | 09:28 · How about some of you immunoglobulin E?! |
| `global/start_1.ogg` | início da partida | S01E02 | 13:01 · Cells at work! | 13:00 · Cells at work! |
| `killer_t/kill_1.ogg` | eliminação | S01E07 | 11:11 · Die! You buggy bastard! | 11:11 · Damn bug! Time to die! |
| `killer_t/punch_1.ogg` | soco carregado | S01E09 | 12:23 · Forty-Two Killer-T-Punch Combo! | — |
| `killer_t/spawn_1.ogg` | entrar em campo | S01E03 | 07:39 · Right, then! Is this where those viruses are or what? | 07:38 · Looks like this is the place boys. |
| `killer_t/spawn_2.ogg` | entrar em campo | S01E01 | 11:41 · In the name of killer T cell division, / take out the target within 2 seconds of contact! | 11:41 · To uphold the name of the Killer T-cell Division! You will kill the target on sight! |
| `killer_t/ult_1.ogg` | especial (F) | S01E03 | 07:43 · Us Killer T Cells are here now to kill 'em all! | 07:40 · Let's kick this virus scum out! The Killer T-cell Division's here to slaughter every last one! |
| `killer_t/ult_2.ogg` | especial (F) | S01E01 | 13:37 · Failure is not an option! | 13:37 · Do whatever it takes to smoke them out! |
| `macrophage/e_1.ogg` | habilidade E | S01E10 | 20:07 · Let me deliver the final blow, / please! | 20:07 · And now to apply the finishing touch. Here goes! |
| `macrophage/heal_1.ogg` | Fagocitose (cura ao eliminar) | S01E10 | 20:26 · I feel really refreshed. | 20:26 · Simply refreshing. |
| `macrophage/kill_1.ogg` | eliminação | S01E10 | 20:23 · And with that, / cleaning time is over. | 20:22 · Now then, we're all done tidying up. |
| `macrophage/spawn_1.ogg` | entrar em campo | S01E03 | 06:34 · This is Macrophage, reporting. | 06:34 · Macrophage reporting in. |
| `macrophage/ult_1.ogg` | especial (F) | S01E10 | 19:54 · Okay, everyone. / Time to overpower our enemy! | 19:54 · All right, ladies! Shall we finish this up and call it a day? |
| `neutrophil/kill_1.ogg` | eliminação | S01E01 | 21:51 · Die! You germ! | 21:51 · DIE, YOU FILTHY JERM! |
| `neutrophil/kill_2.ogg` | eliminação | S01E01 | 06:27 · Die! / You germ! | 06:27 · Time to die! You filthy germ! |
| `neutrophil/kill_3.ogg` | eliminação | S01E01 | 20:50 · Bye-bye, bug! | 20:48 · Bye-bye, bacterium. |
| `neutrophil/kill_4.ogg` | eliminação | S01E10 | 11:24 · Die! / You buggy bacteria! | 11:24 · Filthy germ! Time to die! |
| `neutrophil/net_1.ogg` | Rede NET acerta | S01E01 | 19:12 · Bacterium successfully captured. | 19:12 · Bacterium successfully captured. |
| `neutrophil/passive_1.ogg` | Receptor detecta inimigo | S01E01 | 08:33 · My receptor's reacting! | 08:31 · Got a ping. My receptor's picking him up. |
| `neutrophil/q_1.ogg` | habilidade Q | S01E01 | 06:25 · I've found you, you bastard! | 06:25 · I've got you now, you bastard! |
| `neutrophil/q_2.ogg` | habilidade Q | S01E10 | 11:35 · Say your prayers! | 11:32 · It's no escaping the white blood cells! |
| `neutrophil/spawn_1.ogg` | entrar em campo | S01E01 | 06:24 · Target in sight! | 06:23 · Target sighted! |
| `neutrophil/ult_1.ogg` | especial (F) | S01E01 | 21:46 · Kill them! Kill them all! | 21:46 · Kill them! Annihilate them! |
| `neutrophil/ult_2.ogg` | especial (F) | S01E01 | 21:43 · A reaction! / There are germs nearby! | 21:44 · Alert! It's bacteria. They're close. |
| `neutrophil/win_1.ogg` | vitória do time | S01E01 | 03:21 · Bacterial invaders successfully neutralized. | 03:21 · The invading germs have been exterminated. |
| `platelet/go_1.ogg` | início da escolta | S01E02 | 16:52 · Here we go! / Okay! | 16:49 · Alright then, platelet squad, move out! Yay! |
| `platelet/heave_1.ogg` | plaquetas avançando | S01E02 | 01:05 · Heave-ho! / Heave-ho! | 01:05 · Pee-poh! Pee-poh! Pee-poh! |
| `pneumococcus/death_1.ogg` | morte | S01E01 | 04:27 · Curse you, white blood cells! | 04:25 · Curses! wretched white blood cells, I swear that I will have my revenge! |
| `pneumococcus/e_1.ogg` | habilidade E | S01E01 | 06:34 · You think I'll be captured that easily? | 06:34 · But there's no way I'm letting you kill me today! |
| `pneumococcus/kill_1.ogg` | eliminação | S01E01 | 17:12 · You'll do, I guess. Die! | 17:13 · Looks like it's time to die! |
| `pneumococcus/q_1.ogg` | habilidade Q | S01E01 | — | 18:54 · I swear I will tear you limb from limb! |
| `pneumococcus/spawn_1.ogg` | entrar em campo | S01E01 | 02:45 · My mind's made up. Starting today, this place is ours! | 02:47 · This world belongs to us! |
| `pneumococcus/ult_1.ogg` | especial (F) | S01E01 | 17:54 · Right now I'm going to kill you slowly, one by one! | 17:51 · Before I begin my all-out invasion, I think I might torture your pathetic self to death! |
| `pneumococcus/ult_2.ogg` | especial (F) | S01E01 | 16:10 · You're wasting your strength.  I'm going to massacre the lot of you! | 16:12 · At least you can die knowing you tried your best. |
| `pneumococcus/win_1.ogg` | vitória do time | S01E01 | 02:45 · My mind's made up. Starting today, this place is ours! | 02:47 · This world belongs to us! |
| `pseudomonas/kill_1.ogg` | eliminação | S01E06 | 11:31 · This is just so much fun! | 11:30 · Hahahaha! I'm having such a blast! |
| `pseudomonas/kill_2.ogg` | eliminação | S01E06 | 10:32 · Die! | 10:29 · PLAYTIME IS OVER! NOW DIE! |
| `pseudomonas/rmb_1.ogg` | botão direito | S01E06 | 12:27 · Have it your way! | 12:27 · Bad choice! |
| `pseudomonas/spawn_1.ogg` | entrar em campo | S01E06 | 08:42 · This is no costume. I'm the real Pseudomonas Aeruginosa! | 08:39 · This is no costume. I am a genuine real deal pseudomonas! |
| `pseudomonas/ult_1.ogg` | especial (F) | S01E06 | 11:37 · This is why I'll never stop being a bully! | 11:38 · There's nothing more fun than tormenting the weak and the helpless! |
| `pseudomonas/ult_2.ogg` | especial (F) | S01E02 | 10:17 · Now, we'll just kill the rest of you! | 10:18 · You can hand over the nutrients or die! |
| `staphylococcus/e_1.ogg` | habilidade E | S01E10 | 15:27 · Take this! | 15:27 · Stick around! |
| `staphylococcus/kill_1.ogg` | eliminação | S01E02 | 08:28 · Kill the scum. | 08:27 · Wipe out those cells |
| `staphylococcus/kill_2.ogg` | eliminação | S01E10 | 12:07 · Not bad at all. Kill the scum. | 12:07 · I can get to like it here. Wipe out those cells. |
| `staphylococcus/kill_3.ogg` | eliminação | S01E02 | 15:45 · You're mine! | 15:44 · Now get ready to die! |
| `staphylococcus/q_1.ogg` | habilidade Q | S01E10 | 16:13 · I'm invincible! | 16:13 · You're finished! |
| `staphylococcus/spawn_1.ogg` | entrar em campo | S01E10 | 10:20 · My name is... Staphylococcus aureus! | 10:17 · Good afternoon my lovely, lowly little cells! Welcome your new master, Staphylococcus aureus! |
| `staphylococcus/spawn_2.ogg` | entrar em campo | S01E10 | 10:51 · Charge! | 10:51 · Now get to work! |
| `staphylococcus/spawn_3.ogg` | entrar em campo | S01E02 | 18:48 · In that case, I'll take you on by myself! | 18:48 · You think I care? I'll defeat you all on my own! |
| `staphylococcus/ult_1.ogg` | especial (F) | S01E10 | 13:14 · Combine! | 13:14 · Time to fuse |
| `staphylococcus/ult_2.ogg` | especial (F) | S01E10 | 12:36 · Come on, girls! | 12:36 · Alright, ladies! Let's pull it together! |
| `streptococcus/kill_1.ogg` | eliminação | S01E02 | 10:39 · Now, die! | 10:39 · Time to die! |
| `streptococcus/spawn_1.ogg` | entrar em campo | S01E02 | 09:50 · This body's ours for the taking! | 09:50 · Looks like your world now belongs to us! |
| `streptococcus/ult_1.ogg` | especial (F) | S01E02 | 10:52 · Any blood cells not carrying nutrients... / get to die! | 10:52 · Any blood cells not delivering nutrients will die! |
