# Animações Mesh2Motion (CC0)

Clipes da biblioteca humana do [Mesh2Motion](https://github.com/Mesh2Motion/mesh2motion-app)
(`static/assets/human/animations/`, commit `e03a100`), baixados em 2026-11-19 (`sit-ground-idle.glb` em 2026-11-24, mesmo commit).
Os assets de arte do projeto (modelos, esqueletos e animações) são **CC0 1.0**
(`LICENSE-CC0.MD` do repositório); o código do app é MIT e não foi usado.

O esqueleto de origem segue a nomenclatura da Unreal (`pelvis`, `spine_01`,
`upperarm_l`...). `referencias/scripts/personagens/tripo_characters.py` reaproveita
esses movimentos no esqueleto Mixamo dos modelos do Tripo (hemácia, plaqueta e
Célula B): copia a rotação de cada osso a partir da pose de repouso, ajusta a
altura do quadril, alinha o ciclo dos pés e prende a arma e a caixa nas mãos.

| Arquivo | Usado como |
| --- | --- |
| `idle-a.glb` | Idle da hemácia e da plaqueta |
| `walk-female.glb` | Walk da hemácia |
| `run-female.glb` | Run da hemácia (fuga) |
| `walk-carry.glb` | Só a pegada das mãos na caixa (o clipe é de carga pesada; o Carry da hemácia é uma pose leve montada sobre o Idle) |
| `greeting.glb` | Wave da hemácia (trecho do aceno) |
| `walk-happy.glb` | Walk da plaqueta |
| `hammering.glb` | Repair da plaqueta |
| `rifle-idle.glb`, `rifle-walk.glb`, `rifle-run.glb` | Idle, Walk e Run da Célula B |
| `rifle-fire.glb`, `rifle-reload.glb` | Fire e Reload da Célula B |
| `jump-air.glb`, `jump-land.glb` | Jump e Land da Célula B (só quadril e pernas) |
| `punch-cross.glb` | Melee da Célula B |
| `sit-ground-idle.glb` | Sit da Célula B (sentada no chão na Chuva de anticorpos; o rifle vai atravessado sobre os joelhos, por IK) |
