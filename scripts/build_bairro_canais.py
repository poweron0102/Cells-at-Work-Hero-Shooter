"""Build the original canal district in Blender. No existing game map is read.
Run: blender --background --python scripts/build_bairro_canais.py
"""
import bpy, math, random, json
from pathlib import Path
from mathutils import Vector

random.seed(19)
OUT = Path(__file__).resolve().parents[1] / 'Assets/Maps/BairroDosCanais'
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name != 'Collection': bpy.data.collections.remove(c)
root = bpy.data.collections.get('Collection'); root.name = 'BAIRRO DOS CANAIS'
collections = {}
for name in ['01_Ruas_e_Canal','02_Pontes','03_Fachadas','04_Arteria','05_Praca','06_Obra','07_Detalhes','08_Colisao','09_Marcadores','10_Apresentacao']:
    c = bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); collections[name] = c
group = '01_Ruas_e_Canal'
colliders=[]
def move(o):
    for c in list(o.users_collection): c.objects.unlink(o)
    collections[group].objects.link(o)
    return o
def mat(name, color, rough=.7, metallic=0):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*color,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metallic
    return m
cream=mat('Cal • marfim',(.77,.65,.45)); pale=mat('Calcario • claro',(.88,.80,.63)); ochre=mat('Ocre • arterial',(.65,.34,.12)); coral=mat('Terracota • coral',(.60,.23,.15)); red=mat('Arteria • vermelho',(.55,.075,.048)); teal=mat('Esquadrias • petroleo',(.045,.19,.20)); blue=mat('Servico • azul',(.07,.31,.42)); iron=mat('Ferro • grafite',(.055,.075,.072),.35,.6); glass=mat('Vidro • verde claro',(.24,.48,.43),.22,.25); wood=mat('Madeira • mel',(.40,.23,.10)); green=mat('Folhas • salvia',(.18,.32,.12)); dark=mat('Ruptura • interior',(.10,.045,.055)); gold=mat('Sinalizacao • mostarda',(.94,.57,.10)); white=mat('Sinalizacao • marfim',(.98,.91,.70)); stone=mat('Piso • calcario',(.64,.59,.47)); road=mat('Piso • ocre',(.61,.43,.25)); brick=mat('Alvenaria • tijolo',(.52,.25,.15)); water=mat('Canal • agua jade',(.18,.58,.48),.16,.30)
def procedural(m,kind):
    n=m.node_tree.nodes; l=m.node_tree.links; p=n.get('Principled BSDF'); tex=n.new('ShaderNodeTexCoord')
    if kind=='brick':
        t=n.new('ShaderNodeTexBrick'); t.inputs['Color1'].default_value=(.54,.27,.16,1); t.inputs['Color2'].default_value=(.34,.13,.08,1); t.inputs['Mortar'].default_value=(.65,.52,.36,1); t.inputs['Scale'].default_value=1.6; t.inputs['Mortar Size'].default_value=.025
        # Object coordinates keep brick scale constant; rotate to put courses vertically.
        mapping=n.new('ShaderNodeVectorMath'); mapping.operation='MULTIPLY'; mapping.inputs[1].default_value=(1,1,1)
        sep=n.new('ShaderNodeSeparateXYZ'); comb=n.new('ShaderNodeCombineXYZ'); l.new(tex.outputs['Object'],sep.inputs[0]); horizontal=n.new('ShaderNodeMath'); horizontal.operation='ADD'; l.new(sep.outputs['X'],horizontal.inputs[0]); l.new(sep.outputs['Y'],horizontal.inputs[1]); l.new(horizontal.outputs[0],comb.inputs['X']); l.new(sep.outputs['Z'],comb.inputs['Y']); l.new(comb.outputs[0],t.inputs['Vector']); l.new(t.outputs['Color'],p.inputs['Base Color'])
        b=n.new('ShaderNodeBump'); b.inputs['Strength'].default_value=.35; b.inputs['Distance'].default_value=.07; l.new(t.outputs['Fac'],b.inputs['Height']); l.new(b.outputs[0],p.inputs['Normal'])
    elif kind=='stone':
        v=n.new('ShaderNodeTexVoronoi'); v.feature='DISTANCE_TO_EDGE'; v.inputs['Scale'].default_value=1.5; l.new(tex.outputs['Object'],v.inputs['Vector'])
        r=n.new('ShaderNodeValToRGB'); r.color_ramp.elements[0].position=.012; r.color_ramp.elements[0].color=(.25,.25,.20,1); r.color_ramp.elements[1].position=.035; r.color_ramp.elements[1].color=(.73,.67,.53,1); l.new(v.outputs['Distance'],r.inputs[0]); l.new(r.outputs[0],p.inputs['Base Color'])
        b=n.new('ShaderNodeBump'); b.inputs['Strength'].default_value=.28; b.inputs['Distance'].default_value=.045; l.new(v.outputs['Distance'],b.inputs['Height']); l.new(b.outputs[0],p.inputs['Normal'])
    else:
        nse=n.new('ShaderNodeTexNoise'); nse.inputs['Scale'].default_value=4 if kind=='water' else 10; l.new(tex.outputs['Object'],nse.inputs['Vector']); b=n.new('ShaderNodeBump'); b.inputs['Strength'].default_value=.18; b.inputs['Distance'].default_value=.055 if kind=='water' else .025; l.new(nse.outputs['Fac'],b.inputs['Height']); l.new(b.outputs[0],p.inputs['Normal'])
for m,k in [(brick,'brick'),(stone,'stone'),(cream,'plaster'),(road,'plaster'),(water,'water')]: procedural(m,k)
def collision(o):
    q=o.copy(); q.data=o.data.copy(); q.name='COL_'+o.name
    collections['08_Colisao'].objects.link(q); q.modifiers.clear(); q.data.materials.clear(); q.hide_render=True; q.display_type='WIRE'; q.hide_set(True); q['collision']=True; colliders.append(q)
def box(name,loc,dim,m, bevel=.04,col=False):
    x,y,z=[v/2 for v in dim]
    vs=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    d=bpy.data.meshes.new(name); d.from_pydata(vs,[],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]); d.update()
    o=bpy.data.objects.new(name,d); collections[group].objects.link(o); o.location=loc; o.data.materials.append(m)
    if col: collision(o)
    if bevel:
        b=o.modifiers.new('Arestas suaves','BEVEL'); b.width=bevel; b.segments=2
        o.modifiers.new('Normais','WEIGHTED_NORMAL')
    return o
def mesh(name,verts,faces,m,col=False):
    d=bpy.data.meshes.new(name); d.from_pydata(verts,[],faces); d.update(); o=bpy.data.objects.new(name,d); collections[group].objects.link(o); o.data.materials.append(m)
    if col: collision(o)
    return o
def rod(name,a,b,r,m):
    a,b=Vector(a),Vector(b); d=b-a
    vs=[(r*math.cos(i*math.tau/10),r*math.sin(i*math.tau/10),z) for z in [-d.length/2,d.length/2] for i in range(10)]
    fs=[tuple(reversed(range(10))),tuple(range(10,20))]+[(i,(i+1)%10,(i+1)%10+10,i+10) for i in range(10)]
    o=mesh(name,vs,fs,m); o.location=(a+b)/2; o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return o
def line(name,points,r,m):
    d=bpy.data.curves.new(name,'CURVE'); d.dimensions='3D'; d.bevel_depth=r; d.bevel_resolution=2; s=d.splines.new('POLY'); s.points.add(len(points)-1)
    for p,v in zip(s.points,points): p.co=(*v,1)
    o=bpy.data.objects.new(name,d); collections[group].objects.link(o); d.materials.append(m); return o
def text(body,loc,size,m=white,rot=(math.pi/2,0,0)):
    d=bpy.data.curves.new('Letreiro '+body,'FONT'); d.body=body; d.align_x='CENTER'; d.align_y='CENTER'; d.size=size; d.extrude=.008
    o=bpy.data.objects.new('Letreiro '+body,d); collections[group].objects.link(o); o.location=loc; o.rotation_euler=rot; d.materials.append(m); return o
def sign(body,x,y,z,w=5,color=teal):
    box('Placa '+body,(x,y,z),(w,.20,1.15),color,.08); text(body,(x,y-.12,z),.44 if len(body)<14 else .31)
def rail(a,b,z=0):
    ax,ay=a; bx,by=b; length=math.hypot(bx-ax,by-ay)
    for h in [.22,1.02]: rod('Corrimao',(ax,ay,z+h),(bx,by,z+h),.045,iron)
    for i in range(int(length/.65)+1):
        t=i/max(1,int(length/.65)); x=ax+(bx-ax)*t; y=ay+(by-ay)*t; rod('Balaustre',(x,y,z),(x,y,z+1.06),.035,iron)
def ramp(name,x,y0,y1,z0,z1,w):
    vs=[(x-w/2,y0,z0),(x+w/2,y0,z0),(x+w/2,y1,z1),(x-w/2,y1,z1),(x-w/2,y0,-3.4),(x+w/2,y0,-3.4),(x+w/2,y1,-3.4),(x-w/2,y1,-3.4)]
    return mesh(name,vs,[(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],stone,True)

# Street datum 0 m, canal bed -3 m. The channel crosses the entire district.
box('Fundacao',(0,0,-3.8),(80,100,1.6),brick,.15,True)
box('Margem sul',(0,-28,-1.5),(80,44,3),stone,.02,True)
box('Margem norte',(0,28,-1.5),(80,44,3),stone,.02,True)
box('Leito raso',(0,0,-3.15),(80,12,.3),stone,.02,True)
box('Agua rasa 12 cm',(0,0,-2.88),(79.6,11.8,.035),water,0)
for y in [-6.05,6.05]:
    # Interrupted coping leaves the ramp mouths open.
    for x in range(-39,40):
        if any(abs(x-r)<2.3 for r in [-14,14]): continue
        box('Pedra do cais',(x,y,.075),(.96,.42,.15),pale,.025)
for x in [-14,14]:
    ramp('Rampa sul do canal',x,-18,-6,0,-3,3.6)
    ramp('Rampa norte do canal',x,6,18,-3,0,3.6)
    # Cut trenches out of the bank with booleans, leaving real descending ramps.
    for yc in [-12,12]:
        cutter=box('Corte temporario',(x,yc,-1.4),(3.7,12.02,3.3),stone,0)
        for o in [bpy.data.objects['Margem sul' if yc<0 else 'Margem norte'],bpy.data.objects['COL_Margem sul' if yc<0 else 'COL_Margem norte']]:
            mod=o.modifiers.new('Abertura da rampa','BOOLEAN'); mod.operation='DIFFERENCE'; mod.object=cutter
            bpy.context.view_layer.objects.active=o; o.hide_set(False); bpy.ops.object.modifier_apply(modifier=mod.name)
            if o.name.startswith('COL_'): o.hide_set(True)
        bpy.data.objects.remove(cutter,do_unlink=True)
for y0,y1 in [(-39,-6),(6,41)]:
    box('Avenida arterial',(0,(y0+y1)/2,.012),(10,y1-y0,.025),road,0)
for y in [-35,11,38]: box('Rua transversal',(0,y,.032),(70,6,.025),road,0)
for x in [-24,24]:
    for y0,y1 in [(-40,-6),(6,43)]: box('Rua lateral',(x,(y0+y1)/2,.012),(6,y1-y0,.025),road,0)

group='02_Pontes'
for x,w in [(-24,5),(0,7),(24,5)]:
    box('Ponte • piso',(x,0,-.22),(w,12.4,.44),stone,.035,True)
    for side in [-1,1]:
        xx=x+side*(w/2-.18)
        # Voussoirs frame a real, unobstructed opening along the canal.
        for i in range(20):
            y0=-6+i*.6; y1=y0+.58
            bottom0=-2.65+2.0*math.sqrt(max(0,1-(y0/6)**2)); bottom1=-2.65+2.0*math.sqrt(max(0,1-(y1/6)**2))
            verts=[(xx-.25,y0,bottom0),(xx+.25,y0,bottom0),(xx+.25,y1,bottom1),(xx-.25,y1,bottom1),(xx-.25,y0,-.24),(xx+.25,y0,-.24),(xx+.25,y1,-.24),(xx-.25,y1,-.24)]
            mesh('Arco • aduela',verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],brick,True)
        box('Ponte • mureta',(xx,0,.22),(.5,12.4,.44),brick,.035,True)
        box('Ponte • capeamento',(xx,0,.48),(.65,12.5,.12),pale,.025)
        rail((xx,-6),(xx,6),.54)
        for y in [-6,6]:
            box('Ponte • pilar',(xx,y,.65),(.85,.85,1.3),brick,.05,True); box('Ponte • coroa',(xx,y,1.34),(1,1,.18),pale,.05)
    sign('PONTE CENTRAL' if x==0 else ('PONTE POENTE' if x<0 else 'PONTE NASCENTE'),x,-6.35,-.65,w-.8)

group='03_Fachadas'
def building(name,x,y,w,d,h,color,portico=False):
    if portico:
        # Open ground-floor arcade with exits to both ends.
        box(name+' • andares',(x,y,(h+3.4)/2),(w,d,h-3.4),color,.08,True)
        for xx in [x-w/2+.4,x+w/2-.4]:
            box(name+' • parede lateral',(xx,y,1.7),(.8,d,3.4),brick,.05,True)
        for yy in [y-d/2+.4,y+d/2-.4]:
            for xx in [x-w*.32,x+w*.32]: box('Pilastra de entrada',(xx,yy,1.7),(.6,.7,3.4),pale,.04,True)
    else: box(name,(x,y,h/2),(w,d,h),color,.08,True)
    for z in [.35,3.5,h-.35,h+.1]: box('Cornija '+name,(x,y,z),(w+.35,d+.35,.23),pale,.035)
    box('Cobertura '+name,(x,y,h+.27),(w+.2,d+.2,.28),coral,.05)
    for xx in [x-w/2+.12,x+w/2-.12]:
        for yy in [y-d/2+.12,y+d/2-.12]: box('Cunhal',(xx,yy,h/2),(.38,.38,h),pale,.025)
    for z in range(5,int(h)-1,3):
        for xx in [x-w/2+1.6+i*2.6 for i in range(max(1,int((w-1)/2.6)))]:
            if xx>x+w/2-1: continue
            for sy in [-1,1]:
                yy=y+sy*(d/2+.035)
                box('Janela • moldura',(xx,yy,z),(1.5,.17,2.0),pale,.025)
                box('Janela • vidro',(xx,yy+sy*.1,z),(1.24,.10,1.72),glass,.015)
                box('Janela • montante',(xx,yy+sy*.17,z),(.06,.10,1.8),teal,.01)
                box('Janela • travessa',(xx,yy+sy*.17,z),(1.3,.10,.07),teal,.01)
                box('Janela • peitoril',(xx,yy+sy*.14,z-1),(1.75,.4,.14),pale,.025)
                for sx in [-1,1]:
                    box('Veneziana',(xx+sx*.96,yy+sy*.1,z),(.38,.14,1.8),teal,.02)
                    for dz in [-.6,-.3,0,.3,.6]: box('Lamina da veneziana',(xx+sx*.96,yy+sy*.18,z+dz),(.35,.06,.045),glass,.005)
        for sx in [-1,1]:
            for yy in [y-d/2+1.7+i*3 for i in range(max(1,int((d-1)/3)))]:
                if yy>y+d/2-1: continue
                xx=x+sx*(w/2+.04)
                box('Janela lateral',(xx,yy,z),(.16,1.6,2),pale,.02); box('Vidro lateral',(xx+sx*.09,yy,z),(.08,1.35,1.75),glass,.015); box('Montante lateral',(xx+sx*.14,yy,z),(.08,.07,1.8),teal,.01)
    for yy in [y-d/2-.05,y+d/2+.05]:
        if not portico:
            box('Porta',(x,yy,1.35),(1.9,.15,2.7),teal,.04)
            for i in [-1,1]: box('Vidro porta',(x+i*.45,yy+(-.09 if yy<y else .09),1.6),(.7,.08,1.5),glass,.02)
    return name
building('Deposito A',-31,-26,10,12,10,cream,True)
building('Instituto B',31,24,10,14,13,cream,True)
building('Oficina C',-18,43,15,9,11,ochre,True)
building('Galeria sul oeste',-13,-25,12,16,14,cream,True)
building('Galeria sul leste',13,-25,12,16,17,ochre,True)
building('Residencias poente',-13,26,12,16,13,cream,True)
building('Residencias nascente',13,26,12,16,16,cream,True)
for x,y,w,d,h in [(-36,17,7,15,14),(-36,38,7,10,18),(36,-13,7,9,14),(-36,-12,7,7,12),(36,-38,7,14,19),(-31,-43,12,8,15)]: building('Fachada de contorno',x,y,w,d,h,random.choice([cream,ochre,coral]))
for name,x,y,z in [('A  /  OXIGENIO',-31,-32.15,3),('B  /  OXIGENIO',31,16.85,3),('C  /  OXIGENIO',-18,38.35,3)]: sign(name,x,y,z,6)
# Limited playable balcony, open at both ends and accessible by stairs.
box('Varanda baixa',(-20,26,2.85),(2.4,16,.3),stone,.04,True)
rail((-21.1,18),(-21.1,34),3)
for end,direction in [(18,-1),(34,1)]:
    for i in range(15):
        z=(i+1)*.2; yy=end+direction*(7.5-i*.5-.25)
        box('Escada varanda',(-20,yy,z/2),(2.4,.5,z),stone,.01,True)

group='04_Arteria'
for y in [-33,-25,-17]:
    pts=[(6.2*math.cos(t),y,4.0+6.2*math.sin(t)) for t in [i*math.pi/40 for i in range(41)]]
    line('Arco arterial',pts,.22,red)
    for x in [-6.2,6.2]:
        rod('Coluna arterial',(x,y,0),(x,y,4.05),.22,red); box('Base arterial',(x,y,.3),(.8,.8,.6),pale,.08,True)
for x in [-6.2,6.2]: rod('Longarina arterial',(x,-33,4),(x,-17,4),.10,red)
rod('Suspensao da placa',(0,-25,10.2),(0,-25,7.6),.035,iron)
sign('ARTERIA',0,-25,7,4,red)
text('DISTRITO  /  07',(0,-25.12,6.65),.18)
for y in range(-33,-7,4):
    for x in [-3.9,3.9]: box('Faixa de circulacao',(x,y,.035),(.08,2,.015),white,0)

group='05_Praca'
# A landmark kiosk breaks the central sightline; both sides remain open.
box('Posto reconhecimento',(-5,12,1.6),(3.8,3.4,3.2),teal,.12,True)
box('Cobertura do posto',(-5,12,3.4),(4.5,4.2,.35),pale,.06)
sign('RECONHECIMENTO',-5,10.2,2.8,3.6)
box('Painel de reconhecimento',(-5,10.22,1.6),(2.5,.15,1.2),blue,.08)
for i in range(4): box('Indicador do painel',(-5.8+i*.5,10.11,1.6),(.3,.03,.7),glass,.02)
rod('Antena',(-5,12,3.5),(-5,12,6),iron.diffuse_color[0]+.05,iron)
bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.35,location=(-5,12,6)); move(bpy.context.object).data.materials.append(gold)
for x,y in [(-8,8),(8,12),(0,23)]:
    box('Jardineira de cobertura',(x,y,.7),(3.6,1.6,1.4),pale,.12,True)
    box('Terra',(x,y,1.42),(3.2,1.2,.08),wood,.04)
    for dx in [-1,0,1]:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.7,location=(x+dx,y,1.7)); o=move(bpy.context.object); o.scale=(1,.65,.6); o.data.materials.append(green)
    # hard sightline break above the planter at the northern bend
    if y==23: box('Anteparo da praca',(x,y,1.6),(3.6,.4,3.2),brick,.05,True)

group='06_Obra'
# Protected cell station: broad shield forces two side exits.
box('Estacao • fundo',(0,-48,2.2),(20,.6,4.4),cream,.08,True)
for x in [-10,10]: box('Estacao • lateral',(x,-44,2.2),(.6,8,4.4),cream,.08,True)
box('Estacao • cobertura',(0,-44,4.5),(21,9,.4),blue,.08)
box('Estacao • anteparo',(0,-39,1.8),(9,.65,3.6),cream,.08,True)
sign('ESTACAO CELULAR',0,-39.4,2.6,8,blue)
text('01',(0,-39.4,1.3),1.1,blue)
# Wound and scaffold form a construction landmark, not a corridor plug.
box('Ferida • parede',(2,47,5),(20,1,10),brick,.04,True)
verts=[(2+math.cos(i*math.tau/13)*(3.5+random.random()),46.45,4.5+math.sin(i*math.tau/13)*(3.4+random.random()*.5)) for i in range(13)]
mesh('Ruptura escura',verts,[tuple(range(13))],dark)
line('Borda viva da ruptura',verts+[verts[0]],.28,coral)
for x in [-6,0,6,11]:
    for y in [43,46]: rod('Andaime vertical',(x,y,0),(x,y,10),.07,iron)
for z in [3,6,9]:
    box('Prancha de andaime',(2.5,44.5,z),(18,3,.16),wood,.02)
    for y in [43,46]:
        rod('Andaime horizontal',(-6,y,z+1),(11,y,z+1),.055,iron)
        for x in [-6,0,6]: rod('Contraventamento',(x,y,z-2.8),(x+5,y,z),.045,iron)
sign('REPARO  /  PLAQUETAS',2,42.9,5.2,9,blue)
box('Bacteria • anteparo',(27,38,2),(8,.6,4),brick,.05,True)
box('Bacteria • fundo',(27,48,2),(15,.6,4),brick,.05,True)
for x in [19.5,34.5]: box('Bacteria • lateral',(x,45,2),(.6,6,4),brick,.05,True)
sign('ACESSO DE MANUTENCAO',27,37.65,3.2,7,coral)
def crate(x,y,z=0,s=1.4):
    box('Caixa de reparo',(x,y,z+s/2),(s,s,s),wood,.05,True)
    for dx in [-.38,.38]: box('Cinta da caixa',(x+dx*s,y,z+s/2),(.10,s+.03,s+.03),iron,.012)
    for dz in [-.3,0,.3]: box('Tabua da caixa',(x,y-s/2-.02,z+s/2+dz*s),(s-.1,.04,.025),pale,.005)
    text('Ca2+' if y>30 else 'O2',(x,y-s/2-.05,z+s*.6),s*.27)
for x,y,s in [(-5,39,1.6),(-3.3,39,1.6),(10,39,1.8),(12,39,1.4),(17,43,1.6),(-29,11,1.3),(28,-35,1.5),(-8,-10,1.5),(8,-31,1.4),(28,9,1.3),(-29,32,1.5),(-4,30,1.6)]: crate(x,y,0,s)
crate(-5,39,1.6,1.5)
for x in [-8,12]:
    box('Barreira de obra',(x,41,.8),(3,.45,1.6),gold,.06,True)
    for dx in [-1,-.3,.4,1.1]:
        o=box('Faixa de alerta',(x+dx,40.76,.8),(.22,.025,1.2),iron,.01); o.rotation_euler.y=-.35

group='07_Detalhes'
def lamp(x,y):
    box('Base do poste',(x,y,.15),(.5,.5,.3),pale,.06)
    rod('Poste',(x,y,.2),(x,y,4.4),.065,iron)
    box('Lanterna',(x,y,4.3),(.42,.42,.65),gold,.06)
    box('Chapeu da lanterna',(x,y,4.67),(.65,.65,.12),iron,.05)
    for dx in [-.22,.22]:
        for dy in [-.22,.22]: rod('Lanterna haste',(x+dx,y+dy,3.97),(x+dx,y+dy,4.6),.025,iron)
for x,y in [(-5,-7),(5,7),(-27,-7),(27,7),(-22,12),(22,12),(-22,-34),(22,-34),(-26,37),(22,35),(-7,-37),(7,-37)]: lamp(x,y)
for y in [-6.4,6.4]:
    for a,b in [(-38,-28),(-20,-17),(-11,-4),(4,11),(17,20),(28,38)]: rail((a,y),(b,y),0)
for x,y in [(-31,-34),(31,14),(-18,37)]:
    for i in range(6):
        box('Toldo listrado',(x-2.5+i,y,3.8),(.98,2.2,.12),white if i%2 else teal,.02)
        box('Saia do toldo',(x-2.5+i,y-1.05,3.6),(.98,.12,.4),white if i%2 else teal,.02)
for x,y in [(-9,-35),(9,-12),(-30,14),(28,33),(-9,36)]:
    box('Banco • assento',(x,y,.55),(2.7,.65,.16),wood,.035)
    box('Banco • encosto',(x,y+.28,1),(2.7,.12,.7),wood,.035)
    for dx in [-1,1]: box('Banco • pe',(x+dx,y,.25),(.15,.55,.5),iron,.02)
# Perimeter retains players, skyline lives beyond it.
for x in [-40,40]: box('Limite do bairro',(x,0,-.15),(.5,100,6.3),brick,.02,True)
for y in [-50,50]: box('Limite do bairro',(0,y,1.5),(80,.5,3),brick,.02,True)
for x in range(-39,40,13):
    building('Horizonte norte',x,57,11,10,random.randrange(20,31),cream)
for x in [-47,47]:
    for y in [-36,-17,16,36]: building('Horizonte lateral',x,y,10,14,random.randrange(19,28),cream)

group='09_Marcadores'
markers={'spawn_cells':(0,-44,0),'spawn_bacteria':(27,44,0),'oxygen_A':(-31,-26,0),'oxygen_B':(31,24,0),'oxygen_C':(-18,43,0),'recon':(-5,9,0),'wound':(2,41,0)}
for name,pos in markers.items():
    o=bpy.data.objects.new(name,None); collections[group].objects.link(o); o.location=pos; o.empty_display_type='ARROWS'; o.empty_display_size=1; o['purpose']=name
for i,pos in enumerate([(0,-36,0),(0,-12,0),(0,0,0),(0,11,0),(5,19,0),(5,28,0),(0,36,0),(2,41,0)]):
    o=bpy.data.objects.new('escort_%02d'%i,None); collections[group].objects.link(o); o.location=pos; o.empty_display_type='SPHERE'; o.empty_display_size=.3

group='10_Apresentacao'
scene=bpy.context.scene; scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1
world=bpy.data.worlds.new('Ceu de fim de tarde'); scene.world=world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.57,.73,.82,1); world.node_tree.nodes['Background'].inputs[1].default_value=.5
bpy.ops.object.light_add(type='SUN',location=(0,0,40)); sun=move(bpy.context.object); sun.name='Sol suave'; sun.rotation_euler=(.45,-.5,-.45); sun.data.energy=2.4; sun.data.angle=.14
bpy.ops.object.light_add(type='AREA',location=(0,-10,45)); a=move(bpy.context.object); a.data.energy=2600; a.data.shape='DISK'; a.data.size=40
def camera(name,loc,target,lens=40,ortho=None):
    bpy.ops.object.camera_add(location=loc); o=move(bpy.context.object); o.name=name; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler(); o.data.lens=lens; o.data.clip_end=500
    if ortho: o.data.type='ORTHO'; o.data.ortho_scale=ortho
    return o
hero=camera('Camera • bairro', (95,-115,100),(0,5,6),ortho=146)
street=camera('Camera • canal', (19,-12,5.3),(-5,5,3),24)
artery=camera('Camera • arterial',(0,-37,2.1),(0,-8,4.5),22)
top=camera('Camera • planta',(0,0,130),(0,0,0),ortho=176)
scene.camera=hero; scene.render.engine='CYCLES'; scene.cycles.samples=24; scene.cycles.use_denoising=True
scene.render.resolution_x=1600; scene.render.resolution_y=1200; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
scene.render.image_settings.file_format='PNG'; scene.render.film_transparent=False
scene['Design']='Original baseado exclusivamente em docs/PLANO_MAPA.md, docs/PLANTA_MAPA.svg e referencias/'
scene['Units']='Metros; Z para cima; norte +Y; rua 0; leito -3'
scene['Scope']='Mapa artistico e geometria. Sem implementacao de regras ou balanceamento.'
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_perspective='CAMERA'; area.spaces.active.clip_end=500
        area.spaces.active.shading.type='SOLID'; area.spaces.active.shading.color_type='MATERIAL'; area.spaces.active.shading.show_cavity=True
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'BairroDosCanais.blend'))
print('BLEND_SAVED',flush=True)
# Export a separate collider mesh; artistic GLB uses material base colors.
for o in bpy.context.scene.objects: o.select_set(False)
for o in colliders: o.hide_set(False); o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'BairroDosCanais_collision.glb'),use_selection=True,export_format='GLB',export_extras=True)
for o in colliders: o.select_set(False); o.hide_set(True)
for c in collections.values():
    if c.name in ['08_Colisao','10_Apresentacao']: continue
    for o in c.objects:
        if o.type in {'MESH','CURVE','FONT','EMPTY'}: o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'BairroDosCanais.glb'),use_selection=True,export_format='GLB',export_apply=True,export_extras=True)
print('EXPORTS_SAVED',flush=True)
for cam,file in [(hero,'01_Bairro'),(street,'02_Canal'),(artery,'03_Arteria'),(top,'04_Planta')]:
    scene.camera=cam; scene.render.filepath=str(OUT/(file+'.png')); bpy.ops.render.render(write_still=True); print('RENDERED '+file,flush=True)
scene.camera=hero
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'BairroDosCanais.blend'))
(OUT/'marcadores.json').write_text(json.dumps({'coordinate_system':'Blender Z up, north +Y, meters','markers':markers},indent=2),encoding='utf-8')
print('DONE',flush=True)
