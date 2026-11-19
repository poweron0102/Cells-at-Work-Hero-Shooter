# Falas dos personagens

Clipes de voz recortados dos episódios de *Cells at Work!* (*Hataraku Saibou*, temporada 1),
com a voz isolada da trilha e dos efeitos pelo Demucs. `ja/` usa o áudio original japonês e
`en/` a dublagem em inglês. O conteúdo pertence aos detentores dos direitos do anime
(Akane Shimizu/Kodansha, Aniplex, David Production; dublagem: Crunchyroll/Funimation) e é usado
aqui apenas neste protótipo de fã, sem fins comerciais.

- Manifesto (episódio, tempos, textos, ajustes): [`referencias/audio/voice_clips.json`](voice_clips.json)
- Geração: [`referencias/scripts/audio/build_voices.py`](../scripts/audio/build_voices.py) (instruções no topo do arquivo;
  esta página sai de `build_voices.py --sources`)
- Uso no jogo: `UserComponents/cells/voice.py` e `audio.py`; idioma em `saves/config.json`
  (`{"voice_language": "en"}`) ou `CELLS_VOICE=en`. Padrão: `ja`.

O falante de cada trecho foi conferido pelos quadros do vídeo no momento da fala. As legendas
seguem o áudio japonês; na dublagem, o trecho foi localizado transcrevendo a mesma cena (Whisper),
e os clipes finais dos dois idiomas foram transcritos de novo para conferir o conteúdo.

| Arquivo | Evento | Ep. | JA (tempo · legenda) | EN (tempo · fala) |
| --- | --- | --- | --- | --- |
| `b_cell/e_1.ogg` | habilidade E | S01E05 | 09:25 · Eat this! | 09:21 · You and your buddies are history! |
| `b_cell/e_2.ogg` | habilidade E | S02E05 | 07:04 · Eat this, damn virus! | 07:04 · Say good night! |
| `b_cell/kill_1.ogg` | eliminação | S01E05 | 09:21 · See ya later! | 09:19 · Say goodbye! |
| `b_cell/q_1.ogg` | habilidade Q | S01E03 | 17:15 · This puppy should make light work of them. | 17:15 · Never fear the artillery's here! We'll put them down in no time at all! |
| `b_cell/spawn_1.ogg` | entrar em campo | S01E05 | 08:50 · Leave this to me, fellas! / I've got your back! | 08:49 · Stand back and leave this to me! I've got the cure right here! |
| `b_cell/spawn_2.ogg` | entrar em campo | S01E03 | 17:00 · Sorry for the wait. | 16:59 · Sorry it took so long, |
| `b_cell/spawn_3.ogg` | entrar em campo | S02E02 | 03:28 · Come on, let's go! If it's a known antigen,  we have to mow them down with antibodies! | 03:30 · We'll take them down with antibodies. |
| `b_cell/spawn_4.ogg` | entrar em campo | S02E02 | 03:32 · Come on, time to get to work! | 03:32 · Come on, time to go to work. |
| `b_cell/spawn_5.ogg` | entrar em campo | S02E02 | 09:43 · Thanks for waiting. | 09:42 · Sorry about the wait. |
| `b_cell/ult_1.ogg` | especial (F) | S01E03 | 17:01 · B cell, here! / I've come with antibodies! | 17:01 · I've been a little busy whipping up some antibodies! |
| `b_cell/ult_2.ogg` | especial (F) | S01E05 | — | 09:28 · How about some of you immunoglobulin E?! |
| `b_cell/ult_3.ogg` | especial (F) | S02E02 | 10:01 · Eat this, you dirty viruses! This is... / ...the power of acquired immunity! | 10:06 · ...is acquired immunity, baby! |
| `global/start_1.ogg` | início da partida | S01E02 | 13:01 · Cells at work! | 13:00 · Cells at work! |
| `killer_t/kill_1.ogg` | eliminação | S01E07 | 11:11 · Die! You buggy bastard! | 11:11 · Damn bug! Time to die! |
| `killer_t/punch_1.ogg` | soco carregado | S01E09 | 12:23 · Forty-Two Killer-T-Punch Combo! | — |
| `killer_t/punch_2.ogg` | soco carregado | S01E14 | — | 21:28 · DORIAAAAA! |
| `killer_t/punch_3.ogg` | soco carregado | S02E08 | 11:44 · Eat this! / T Cell... / ...Perforin Cannon Punch! | — |
| `killer_t/spawn_1.ogg` | entrar em campo | S01E03 | 07:39 · Right, then! Is this where those viruses are or what? | 07:38 · Looks like this is the place boys. |
| `killer_t/spawn_2.ogg` | entrar em campo | S01E01 | 11:41 · In the name of killer T cell division, / take out the target within 2 seconds of contact! | 11:41 · To uphold the name of the Killer T-cell Division! You will kill the target on sight! |
| `killer_t/spawn_3.ogg` | entrar em campo | S01E14 | 03:07 · you are to kill it without fail, as soon as you get the order! | 03:05 · Should you happen to encounter an infected cell you annihilate the moment you hear the order is that clear? |
| `killer_t/ult_1.ogg` | especial (F) | S01E03 | 07:43 · Us Killer T Cells are here now to kill 'em all! | 07:40 · Let's kick this virus scum out! The Killer T-cell Division's here to slaughter every last one! |
| `killer_t/ult_2.ogg` | especial (F) | S01E01 | 13:37 · Failure is not an option! | 13:37 · Do whatever it takes to smoke them out! |
| `macrophage/e_1.ogg` | habilidade E | S01E10 | 20:07 · Let me deliver the final blow, / please! | 20:07 · And now to apply the finishing touch. Here goes! |
| `macrophage/heal_1.ogg` | Fagocitose (cura ao eliminar) | S01E10 | 20:26 · I feel really refreshed. | 20:26 · Simply refreshing. |
| `macrophage/heal_2.ogg` | Fagocitose (cura ao eliminar) | S01E06 | 12:39 · You're safe now, kids. | 12:39 · It's alright you two, you're okay. |
| `macrophage/kill_1.ogg` | eliminação | S01E10 | 20:23 · And with that, / cleaning time is over. | 20:22 · Now then, we're all done tidying up. |
| `macrophage/kill_2.ogg` | eliminação | S01E06 | 05:12 · There, there. No need to cry little one. | — |
| `macrophage/kill_3.ogg` | eliminação | S01E10 | 19:41 · My, now. Did you have an argument with your friends? | 19:41 · Oh, how sad! Did you have a falling out with your friends? |
| `macrophage/kill_5.ogg` | eliminação | S01E12 | 10:52 · My, my. | — |
| `macrophage/rmb_1.ogg` | botão direito | S01E06 | 05:09 · Oh, deary me... | 05:09 · Oh no, sweetheart! |
| `macrophage/spawn_1.ogg` | entrar em campo | S01E03 | 06:34 · This is Macrophage, reporting. | 06:34 · Macrophage reporting in. |
| `macrophage/spawn_2.ogg` | entrar em campo | S01E06 | 04:03 · Now then, is everyone ready for class? | 04:03 · All right now children, is everyone all settled in? |
| `macrophage/spawn_3.ogg` | entrar em campo | S01E10 | 21:24 · Every girl has to have a secret or two. | 21:25 · Every girl has her secrets, Red Blood Cell. |
| `macrophage/spawn_4.ogg` | entrar em campo | S02E01 | 02:50 · Oh my! | 02:50 · Why hello! What a pleasant surprise! |
| `macrophage/ult_1.ogg` | especial (F) | S01E10 | 19:54 · Okay, everyone. / Time to overpower our enemy! | 19:54 · All right, ladies! Shall we finish this up and call it a day? |
| `macrophage/ult_2.ogg` | especial (F) | S01E07 | 15:19 · Exterminating them sure will be fun. | 15:19 · I have some killing to do! |
| `neutrophil/kill_1.ogg` | eliminação | S01E01 | 21:51 · Die! You germ! | 21:51 · DIE, YOU FILTHY JERM! |
| `neutrophil/kill_10.ogg` | eliminação | S01E12 | 07:08 · Die, die, you buggy bastard! | 07:08 · I'll kill you! Bring it on! |
| `neutrophil/kill_11.ogg` | eliminação | S01E13 | 14:04 · Die, you buggy bastard! / Die, die! | 14:04 · Die, you miserable filthy germ! I'll kill you, I'll kill you! |
| `neutrophil/kill_12.ogg` | eliminação | S01E02 | 18:40 · Looks like it's your friends that aren't much help. | 18:40 · I guess it turns out you're the one with the flaky friends after all. |
| `neutrophil/kill_2.ogg` | eliminação | S01E01 | 06:27 · Die! / You germ! | 06:27 · Time to die! You filthy germ! |
| `neutrophil/kill_3.ogg` | eliminação | S01E01 | 20:50 · Bye-bye, bug! | 20:48 · Bye-bye, bacterium. |
| `neutrophil/kill_4.ogg` | eliminação | S01E10 | 11:24 · Die! / You buggy bacteria! | 11:24 · Filthy germ! Time to die! |
| `neutrophil/kill_5.ogg` | eliminação | S01E04 | — | 04:34 · Germ exterminated. |
| `neutrophil/kill_6.ogg` | eliminação | S01E08 | — | 03:47 · Target sighted! It's time to die! |
| `neutrophil/kill_8.ogg` | eliminação | S02E03 | — | 09:44 · Say goodnight! |
| `neutrophil/kill_9.ogg` | eliminação | S02E03 | 13:13 · Die! You damn germ bastard! | — |
| `neutrophil/net_1.ogg` | Rede NET acerta | S01E01 | 19:12 · Bacterium successfully captured. | 19:12 · Bacterium successfully captured. |
| `neutrophil/passive_1.ogg` | Receptor detecta inimigo | S01E01 | 08:33 · My receptor's reacting! | 08:31 · Got a ping. My receptor's picking him up. |
| `neutrophil/q_1.ogg` | habilidade Q | S01E01 | 06:25 · I've found you, you bastard! | 06:25 · I've got you now, you bastard! |
| `neutrophil/q_2.ogg` | habilidade Q | S01E10 | 11:35 · Say your prayers! | 11:32 · It's no escaping the white blood cells! |
| `neutrophil/q_3.ogg` | habilidade Q | S01E11 | 11:38 · I'm pursuing that germ, outta the way! | — |
| `neutrophil/spawn_1.ogg` | entrar em campo | S01E01 | 06:24 · Target in sight! | 06:23 · Target sighted! |
| `neutrophil/spawn_2.ogg` | entrar em campo | S01E05 | 04:56 · Antigen, sighted! | — |
| `neutrophil/spawn_3.ogg` | entrar em campo | S01E13 | 21:30 · Antigen sighted! | 21:31 · Target sighted! |
| `neutrophil/spawn_4.ogg` | entrar em campo | S02E03 | 09:30 · Target sighted! | 09:30 · Target sighted! |
| `neutrophil/spawn_5.ogg` | entrar em campo | S02E08 | 03:14 · Sorry to keep you waiting, Cell boy! | 03:14 · Sorry, that was so close, Cell Kid. |
| `neutrophil/ult_1.ogg` | especial (F) | S01E01 | 21:46 · Kill them! Kill them all! | 21:46 · Kill them! Annihilate them! |
| `neutrophil/ult_2.ogg` | especial (F) | S01E01 | 21:43 · A reaction! / There are germs nearby! | 21:44 · Alert! It's bacteria. They're close. |
| `neutrophil/ult_3.ogg` | especial (F) | S02E08 | 03:23 · It's punishment time, you lousy germs! | 03:23 · We're about to show you damn germs why that's a bad idea! |
| `neutrophil/win_1.ogg` | vitória do time | S01E01 | 03:21 · Bacterial invaders successfully neutralized. | 03:21 · The invading germs have been exterminated. |
| `neutrophil/win_2.ogg` | vitória do time | S01E11 | 04:14 · I've eliminated the last of the bacteria. | 04:11 · This is U1146 reporting. I've exterminated the last of the pathogens. |
| `neutrophil/win_3.ogg` | vitória do time | S02E01 | 06:20 · The invading bacterium has been exterminated. | 06:21 · Bacterial intruder exterminated. |
| `platelet/go_1.ogg` | início da escolta | S01E02 | 16:52 · Here we go! / Okay! | 16:49 · Alright then, platelet squad, move out! Yay! |
| `platelet/heave_1.ogg` | plaquetas avançando | S01E02 | 01:05 · Heave-ho! / Heave-ho! | 01:05 · Pee-poh! Pee-poh! Pee-poh! |
| `pneumococcus/death_1.ogg` | morte | S01E01 | 04:27 · Curse you, white blood cells! | 04:25 · Curses! wretched white blood cells, I swear that I will have my revenge! |
| `pneumococcus/e_1.ogg` | habilidade E | S01E01 | 06:34 · You think I'll be captured that easily? | 06:34 · But there's no way I'm letting you kill me today! |
| `pneumococcus/kill_1.ogg` | eliminação | S01E01 | 17:12 · You'll do, I guess. Die! | 17:13 · Looks like it's time to die! |
| `pneumococcus/kill_2.ogg` | eliminação | S01E01 | 18:42 · Giving up, are we? No more tricks up your sleeve? / How boring... | 18:42 · You're gonna surrender now? Don't you have any moves left? |
| `pneumococcus/kill_3.ogg` | eliminação | S01E01 | 15:33 · Oh man, you are such a dummy! | 15:33 · Seriously, how stupid can you possibly be? |
| `pneumococcus/q_1.ogg` | habilidade Q | S01E01 | — | 18:54 · I swear I will tear you limb from limb! |
| `pneumococcus/q_2.ogg` | habilidade Q | S01E01 | — | 06:40 · So long, sucker! |
| `pneumococcus/q_3.ogg` | habilidade Q | S01E01 | 17:50 · Change of plan! | 17:50 · It's time for a change of plans, |
| `pneumococcus/spawn_1.ogg` | entrar em campo | S01E01 | 02:45 · My mind's made up. Starting today, this place is ours! | 02:47 · This world belongs to us! |
| `pneumococcus/spawn_2.ogg` | entrar em campo | S01E01 | 06:31 · So, you've found me already, white blood cell. | 06:31 · Well, look who chased me to the far corners of the world! |
| `pneumococcus/spawn_3.ogg` | entrar em campo | S01E01 | 02:51 · But first... / we'll have to get rid of these pesky locals! | — |
| `pneumococcus/ult_1.ogg` | especial (F) | S01E01 | 17:54 · Right now I'm going to kill you slowly, one by one! | 17:51 · Before I begin my all-out invasion, I think I might torture your pathetic self to death! |
| `pneumococcus/ult_2.ogg` | especial (F) | S01E01 | 16:10 · You're wasting your strength.  I'm going to massacre the lot of you! | 16:12 · At least you can die knowing you tried your best. |
| `pneumococcus/ult_3.ogg` | especial (F) | S01E01 | 18:52 · I'll make sure... / I'll make sure you suffer just like they did! | 18:51 · I'm gonna make you suffer. |
| `pneumococcus/win_1.ogg` | vitória do time | S01E01 | 02:45 · My mind's made up. Starting today, this place is ours! | 02:47 · This world belongs to us! |
| `pseudomonas/death_1.ogg` | morte | S01E06 | 10:11 · My eye! | — |
| `pseudomonas/kill_1.ogg` | eliminação | S01E06 | 11:31 · This is just so much fun! | 11:30 · Hahahaha! I'm having such a blast! |
| `pseudomonas/kill_2.ogg` | eliminação | S01E06 | 10:32 · Die! | 10:29 · PLAYTIME IS OVER! NOW DIE! |
| `pseudomonas/kill_3.ogg` | eliminação | S01E06 | 09:25 · It's because I simply love to bully helpless little blood cells like you. | 09:26 · Because I just love torturing helpless little blood cells, of course. |
| `pseudomonas/kill_4.ogg` | eliminação | S01E06 | 11:06 · You sure are a spunky bunch, I'll give you that. | 11:07 · You've got some spirit haven't you? |
| `pseudomonas/q_1.ogg` | habilidade Q | S01E06 | 08:49 · Just where do you think you're going? | — |
| `pseudomonas/q_2.ogg` | habilidade Q | S01E06 | 10:29 · No more fun and games, pipsqueak! | — |
| `pseudomonas/rmb_1.ogg` | botão direito | S01E06 | 12:27 · Have it your way! | 12:27 · Bad choice! |
| `pseudomonas/spawn_1.ogg` | entrar em campo | S01E06 | 08:42 · This is no costume. I'm the real Pseudomonas Aeruginosa! | 08:39 · This is no costume. I am a genuine real deal pseudomonas! |
| `pseudomonas/spawn_2.ogg` | entrar em campo | S01E06 | 09:39 · Well, then. No time like the present. / Let's get this over with, shall we? | 09:42 · Ask nicely and I'll go ahead and finish you. |
| `pseudomonas/spawn_3.ogg` | entrar em campo | S01E02 | 10:05 · Nutrient-carrying red blood cells, line up over there. | — |
| `pseudomonas/ult_1.ogg` | especial (F) | S01E06 | 11:37 · This is why I'll never stop being a bully! | 11:38 · There's nothing more fun than tormenting the weak and the helpless! |
| `pseudomonas/ult_2.ogg` | especial (F) | S01E02 | 10:17 · Now, we'll just kill the rest of you! | 10:18 · You can hand over the nutrients or die! |
| `staphylococcus/death_1.ogg` | morte | S01E10 | 19:49 · Stop making fun of me! | 19:50 · Don't you dare patronize me! |
| `staphylococcus/e_1.ogg` | habilidade E | S01E10 | 15:27 · Take this! | 15:27 · Stick around! |
| `staphylococcus/kill_1.ogg` | eliminação | S01E02 | 08:28 · Kill the scum. | 08:27 · Wipe out those cells |
| `staphylococcus/kill_2.ogg` | eliminação | S01E10 | 12:07 · Not bad at all. Kill the scum. | 12:07 · I can get to like it here. Wipe out those cells. |
| `staphylococcus/kill_3.ogg` | eliminação | S01E02 | 15:45 · You're mine! | 15:44 · Now get ready to die! |
| `staphylococcus/kill_4.ogg` | eliminação | S01E10 | 14:15 · Like this new taste? | 14:13 · See? I told you so! |
| `staphylococcus/kill_5.ogg` | eliminação | S01E10 | 16:56 · You guys simply don't stand a chance. | 16:53 · Victory is such a glorious feeling! |
| `staphylococcus/kill_6.ogg` | eliminação | S01E10 | 16:54 · What a great feeling! | 17:00 · Such a shame they can't save you now! |
| `staphylococcus/kill_7.ogg` | eliminação | S01E10 | 17:16 · Finally, I get my revenge on these blasted neutrophils! | 17:16 · At last, I can take my revenge, you nasty neutrophils! |
| `staphylococcus/kill_8.ogg` | eliminação | S01E02 | 13:37 · Hey, you're pretty tough. / How much longer can you hold out, I wonder. | 13:38 · Well, well, look at you. I wonder how long you can hold out. |
| `staphylococcus/kill_9.ogg` | eliminação | S01E02 | 14:09 · Your friends aren't very helpful, are they? | 14:09 · Your flaky friends aren't exactly pulling their weight, are they now? |
| `staphylococcus/q_1.ogg` | habilidade Q | S01E10 | 16:13 · I'm invincible! | 16:13 · You're finished! |
| `staphylococcus/q_2.ogg` | habilidade Q | S01E10 | 16:08 · My defensive and offensive capabilities have just shot through the roof! | — |
| `staphylococcus/spawn_1.ogg` | entrar em campo | S01E10 | 10:20 · My name is... Staphylococcus aureus! | 10:17 · Good afternoon my lovely, lowly little cells! Welcome your new master, Staphylococcus aureus! |
| `staphylococcus/spawn_2.ogg` | entrar em campo | S01E10 | 10:51 · Charge! | 10:51 · Now get to work! |
| `staphylococcus/spawn_3.ogg` | entrar em campo | S01E02 | 18:48 · In that case, I'll take you on by myself! | 18:48 · You think I care? I'll defeat you all on my own! |
| `staphylococcus/spawn_4.ogg` | entrar em campo | S01E02 | 15:24 · And then, / we'll take over this place! | 15:24 · I do that, and this world will surrender to me! |
| `staphylococcus/spawn_5.ogg` | entrar em campo | S01E02 | 13:42 · There's still tons of us coming in from outside. | 13:42 · I've got some friends who want to say hello! |
| `staphylococcus/ult_1.ogg` | especial (F) | S01E10 | 13:14 · Combine! | 13:14 · Time to fuse |
| `staphylococcus/ult_2.ogg` | especial (F) | S01E10 | 12:36 · Come on, girls! | 12:36 · Alright, ladies! Let's pull it together! |
| `staphylococcus/ult_3.ogg` | especial (F) | S01E10 | 13:35 · Why don't you have a taste / of the new me! | 13:35 · You neutrophils have no chance! I've got some tricks up my sleeve! |
| `staphylococcus/ult_4.ogg` | especial (F) | S01E10 | 17:32 · Now, all that remains... / is for me to tear them to shreds! | 17:32 · Let's start off with something fun, shall we? |
| `streptococcus/kill_1.ogg` | eliminação | S01E02 | 10:39 · Now, die! | 10:39 · Time to die! |
| `streptococcus/q_1.ogg` | habilidade Q | S01E02 | 10:50 · Didn't you hear me? | 10:50 · Weren't you listening? |
| `streptococcus/spawn_1.ogg` | entrar em campo | S01E02 | 09:50 · This body's ours for the taking! | 09:50 · Looks like your world now belongs to us! |
| `streptococcus/ult_1.ogg` | especial (F) | S01E02 | 10:52 · Any blood cells not carrying nutrients... / get to die! | 10:52 · Any blood cells not delivering nutrients will die! |
