"""Persistent, owner-managed message templates for safe bot messages."""
from __future__ import annotations
import json, sqlite3
from contextlib import contextmanager
import discord
from config import DATABASE_PATH

CATALOG = {
 'Recrutamento': [
  ('recruitment_panel','Painel de recrutamento',True,'🎯 Recrutamento ALL EVOM','Quer entrar para a guilda? Clique abaixo e preencha sua candidatura. A equipe falará com você por um canal privado.'),
  ('recruitment_info','Informações do teste',True,'🎮 Como funciona o teste','Aguarde a equipe orientar seu teste. Confira seu ID do Free Fire e mantenha a disponibilidade informada na candidatura.'),
  ('application_admin_notice','Aviso de nova candidatura',True,'📥 Nova candidatura para analisar','**Candidato:** {candidate}\n**Nome/Nick:** {name}\n**ID Free Fire:** `{ff_id}`\n**WhatsApp:** `{whatsapp}`\n**Disponibilidade:** {availability}\n**Nenhum canal de teste foi criado ainda.**'),
  ('application_received','Confirmação de candidatura',True,'Candidatura enviada','✅ Candidatura enviada para análise da ADM. O canal privado de teste será criado somente se ela aceitar.'),
  ('candidate_test_notice','Candidatura para avaliação',False,'📝 Candidatura para avaliação','Mensagem vinculada aos controles interativos de teste; não editável com segurança nesta versão.'),
 ],
 'Anúncios': [('new_member_announcement','NOVO MEMBRO',True,'🏆 NOVO MEMBRO NA ALL EVOM! 🔥','Deem as boas-vindas a {member}!\n\nO jogador foi **aprovado no teste** e agora faz parte da nossa família.\n\n**Nome/Nick:** {name}\n**ID do Free Fire:** `{ff_id}`\n**ID do Discord:** `{user_id}`\n**Aprovado por:** {staff}')],
 'Candidatura': [('application_form','Formulário de candidatura',False,'Candidatura ALL EVOM','Campos e validações do formulário são controlados pelo modal; texto não editável com segurança.')],
 'X-TREINO': [('xtreino_messages','Mensagens do X-TREINO',False,'X-TREINO','Mensagens conectadas a estados, botões e inscrições; não editável com segurança nesta versão.')],
 'Filas': [('queue_messages','Mensagens das filas',False,'Filas','Mensagens conectadas à lógica de fila e atualização; não editável com segurança nesta versão.')],
 'Sorteios': [('giveaway_messages','Mensagens de sorteios',False,'Sorteios','Mensagens ligadas aos resultados e controles do sorteio; não editável com segurança nesta versão.')],
 'Mensagens automáticas': [('automatic_messages','Mensagens automáticas',False,'Mensagens automáticas','Mensagens diversas ainda precisam de mapeamento individual; não editável com segurança nesta versão.')],
}

@contextmanager
def _db():
    db=sqlite3.connect(DATABASE_PATH)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS message_customizations (message_key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        yield db
        db.commit()
    finally:
        db.close()

def get_template(key, default_title, default_description, default_color=0xD2192D, default_footer=''):
    try:
        with _db() as db:
            row=db.execute('SELECT payload FROM message_customizations WHERE message_key=?',(key,)).fetchone()
        data=json.loads(row[0]) if row else {}
    except Exception:
        data={}
    return {'title':data.get('title',default_title),'description':data.get('description',default_description),'color':int(data.get('color',default_color)),'footer':data.get('footer',default_footer)}

def customized_embed(key, title, description, color=0xD2192D, footer='', **values):
    data=get_template(key,title,description,color,footer)
    try: rendered=data['description'].format_map({k: str(v) for k,v in values.items()})
    except (KeyError, ValueError): rendered=description
    embed=discord.Embed(title=data['title'],description=rendered,color=max(0,min(0xFFFFFF,data['color'])))
    if data['footer']: embed.set_footer(text=data['footer'])
    return embed

class MessageCategorySelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot=bot
        super().__init__(placeholder='Escolha uma categoria de mensagens', options=[discord.SelectOption(label=k,description=f'{sum(1 for x in v if x[2])} editável(is) nesta versão') for k,v in CATALOG.items()])
    async def callback(self, interaction):
        if await _reject(interaction): return
        await interaction.response.edit_message(embed=_embed('Personalizar mensagens',f'Categoria: **{self.values[0]}**\nSelecione uma mensagem.'),view=MessageListView(self.bot,self.values[0]))

async def _reject(i):
    from owner_panel import reject_non_owner
    return await reject_non_owner(i)

def _embed(title,desc): return discord.Embed(title=f'✏️ {title}',description=desc,color=discord.Color.gold())

class MessageEditorHomeView(discord.ui.View):
    def __init__(self,bot):
        super().__init__(timeout=300); self.bot=bot; self.add_item(MessageCategorySelect(bot))
        self.add_item(BackButton(bot))
class BackButton(discord.ui.Button):
    def __init__(self,bot): super().__init__(label='↩️ Voltar ao painel',style=discord.ButtonStyle.secondary,row=1); self.bot=bot
    async def callback(self,i):
        if await _reject(i): return
        from owner_panel import OwnerHomeView,owner_embed
        await i.response.edit_message(embed=owner_embed('👑 Painel do Dono','Escolha uma categoria:'),view=OwnerHomeView(self.bot))

class MessageListView(discord.ui.View):
    def __init__(self,bot,category):
        super().__init__(timeout=300); self.bot=bot; self.category=category
        opts=[]
        for key,label,enabled,title,desc in CATALOG[category]:
            opts.append(discord.SelectOption(label=label[:100],value=key,description=('Editável' if enabled else 'Não editável com segurança') ))
        self.add_item(MessageSelect(bot,category,opts)); self.add_item(BackCategories(bot))
class BackCategories(discord.ui.Button):
    def __init__(self,bot): super().__init__(label='↩️ Categorias',style=discord.ButtonStyle.secondary,row=1); self.bot=bot
    async def callback(self,i):
        if await _reject(i): return
        await i.response.edit_message(embed=_embed('Personalizar mensagens','Escolha uma categoria.'),view=MessageEditorHomeView(self.bot))
class MessageSelect(discord.ui.Select):
    def __init__(self,bot,category,options): self.bot=bot; self.category=category; super().__init__(placeholder='Selecione uma mensagem',options=options)
    async def callback(self,i):
        if await _reject(i): return
        item=next(x for x in CATALOG[self.category] if x[0]==self.values[0])
        key,label,enabled,title,desc=item
        if not enabled:
            return await i.response.send_message(f'ℹ️ **{label}**\n{desc}',ephemeral=True)
        await i.response.edit_message(embed=_embed(label,'Edite título, texto, cor e rodapé. A prévia usa os valores salvos atualmente.'),view=MessageActionsView(self.bot,self.category,item))

class MessageActionsView(discord.ui.View):
    def __init__(self,bot,category,item):
        super().__init__(timeout=300); self.bot=bot; self.category=category; self.item=item
        self.add_item(EditMessageButton(bot,category,item)); self.add_item(PreviewMessageButton(bot,item)); self.add_item(RestoreMessageButton(bot,category,item)); self.add_item(BackToList(bot,category))
class EditMessageButton(discord.ui.Button):
    def __init__(self,bot,category,item): super().__init__(label='Editar mensagem',style=discord.ButtonStyle.primary); self.bot=bot; self.category=category; self.item=item
    async def callback(self,i):
        if await _reject(i): return
        await i.response.send_modal(EditMessageModal(self.category,self.item))
class EditMessageModal(discord.ui.Modal):
    def __init__(self,category,item):
        super().__init__(title=f'Editar: {item[1]}'[:45]); self.category=category; self.item=item
        key,label,enabled,title,desc=item; current=get_template(key,title,desc)
        self.title_field=discord.ui.TextInput(label='Título',default=current['title'][:256],max_length=256)
        self.desc_field=discord.ui.TextInput(label='Texto / descrição',style=discord.TextStyle.paragraph,default=current['description'][:4000],max_length=4000)
        self.color_field=discord.ui.TextInput(label='Cor hexadecimal (ex.: D2192D)',default=f"{current['color']:06X}",max_length=6)
        self.footer_field=discord.ui.TextInput(label='Rodapé (opcional)',default=current['footer'][:2048],required=False,max_length=2048)
        for f in (self.title_field,self.desc_field,self.color_field,self.footer_field): self.add_item(f)
    async def on_submit(self,i):
        if await _reject(i): return
        try: color=int(str(self.color_field.value).strip().replace('#',''),16)
        except ValueError: return await i.response.send_message('Cor inválida. Use 6 caracteres hexadecimais, por exemplo D2192D.',ephemeral=True)
        payload={'title':str(self.title_field.value),'description':str(self.desc_field.value),'color':color,'footer':str(self.footer_field.value)}
        with _db() as db: db.execute('INSERT INTO message_customizations(message_key,payload,updated_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(message_key) DO UPDATE SET payload=excluded.payload,updated_at=CURRENT_TIMESTAMP',(self.item[0],json.dumps(payload,ensure_ascii=False)))
        await i.response.send_message('✅ Personalização salva permanentemente. As próximas mensagens usarão o novo modelo.',ephemeral=True)
class PreviewMessageButton(discord.ui.Button):
    def __init__(self,bot,item): super().__init__(label='Prévia',style=discord.ButtonStyle.success); self.bot=bot; self.item=item
    async def callback(self,i):
        if await _reject(i): return
        key,label,en,title,desc=self.item
        samples={'member':'Novo membro','name':'Jogador','ff_id':'123456789','user_id':'123456789012345678','staff':'ADM responsável','candidate':'@candidato','whatsapp':'11999999999','availability':'Noite'}
        e=customized_embed(key,title,desc,**samples)
        await i.response.send_message('Prévia da mensagem (sem publicar no canal):',embed=e,ephemeral=True)
class RestoreMessageButton(discord.ui.Button):
    def __init__(self,bot,category,item): super().__init__(label='Restaurar padrão',style=discord.ButtonStyle.danger); self.bot=bot; self.category=category; self.item=item
    async def callback(self,i):
        if await _reject(i): return
        with _db() as db: db.execute('DELETE FROM message_customizations WHERE message_key=?',(self.item[0],))
        await i.response.send_message('↩️ Mensagem restaurada ao padrão original.',ephemeral=True)
class BackToList(discord.ui.Button):
    def __init__(self,bot,category): super().__init__(label='↩️ Mensagens',style=discord.ButtonStyle.secondary,row=1); self.bot=bot; self.category=category
    async def callback(self,i):
        if await _reject(i): return
        await i.response.edit_message(embed=_embed('Personalizar mensagens',f'Categoria: **{self.category}**\nSelecione uma mensagem.'),view=MessageListView(self.bot,self.category))
