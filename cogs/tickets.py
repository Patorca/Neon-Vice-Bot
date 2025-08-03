import discord
from discord.ext import commands
from discord import app_commands
import json
import logging
from typing import Optional
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

async def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

async def create_transcript(channel: discord.TextChannel, user: discord.User) -> str:
    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        author = f"{message.author.display_name} ({message.author.name}#{message.author.discriminator})"
        content = message.content or "[No content]"
        if message.embeds:
            for embed in message.embeds:
                if embed.title:
                    content += f"\n[Embed: {embed.title}]"
                if embed.description:
                    content += f"\n{embed.description}"
        if message.attachments:
            for attachment in message.attachments:
                content += f"\n[Attachment: {attachment.filename}]"
        messages.append(f"[{timestamp}] {author}: {content}")

    transcript = (
        f"Transcript del Ticket: {channel.name}\n"
        f"Usuario: {user.display_name} ({user.name}#{user.discriminator})\n"
        f"Creado: {channel.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Cerrado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        + "=" * 50 + "\n\n" + "\n".join(messages)
    )
    return transcript

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label='Crear Ticket',
        style=discord.ButtonStyle.primary,
        emoji='🎫',
        custom_id='create_ticket'
    )
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user

        existing_ticket = discord.utils.get(
            guild.channels,
            name=f'ticket-{user.name.lower()}-{user.discriminator}'
        )
        if existing_ticket:
            await interaction.followup.send(
                f"❌ Ya tienes un ticket abierto: {existing_ticket.mention}",
                ephemeral=True
            )
            return

        try:
            config = await load_config()
            guild_id_str = str(guild.id)
            server_config = config.get('servers', {}).get(guild_id_str, {})

            category = None
            if category_id := server_config.get('ticket_category_id'):
                category = guild.get_channel(category_id)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    attach_files=True, embed_links=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    manage_channels=True, manage_messages=True
                )
            }

            for role_id in server_config.get('staff_role_ids', []):
                role = guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True,
                        manage_messages=True
                    )

            ticket_channel = await guild.create_text_channel(
                name=f'ticket-{user.name.lower()}-{user.discriminator}',
                category=category,
                overwrites=overwrites,
                topic=f'Support ticket for {user.display_name} ({user.id})'
            )

            close_view = CloseTicketView()

            embed = discord.Embed(
                title="🎫 Ticket de Soporte Creado",
                description=(
                    f"¡Hola {user.mention}! Gracias por crear un ticket.\n\n"
                    "Por favor describe tu problema en detalle y nuestro staff te ayudará en breve.\n\n"
                    "Para cerrar este ticket, haz clic en el botón de abajo."
                ),
                color=0x00ff00
            )
            embed.set_footer(text=f"Ticket creado por {user.display_name}", icon_url=user.display_avatar.url)

            # Mencionar todos los roles de staff configurados
            staff_role_ids = server_config.get('staff_role_ids', [])
            staff_mentions = []
            
            for staff_role_id in staff_role_ids:
                staff_role = guild.get_role(staff_role_id)
                if staff_role:
                    staff_mentions.append(staff_role.mention)
            
            # Enviar mensaje con menciones de staff si hay roles configurados
            if staff_mentions:
                staff_mention_text = " ".join(staff_mentions)
                await ticket_channel.send(f"{staff_mention_text} - Nuevo ticket creado por {user.mention}")

            await ticket_channel.send(embed=embed, view=close_view)
            await interaction.followup.send(
                f"✅ Tu ticket ha sido creado: {ticket_channel.mention}",
                ephemeral=True
            )
            logger.info(f"Ticket created by {user} ({user.id}) in {guild.name}")

        except discord.Forbidden:
            await interaction.followup.send("❌ No tengo permisos para crear canales!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            await interaction.followup.send("❌ Ocurrió un error al crear tu ticket!", ephemeral=True)

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label='Cerrar Ticket',
        style=discord.ButtonStyle.danger,
        emoji='🔒',
        custom_id='close_ticket'
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.channel.name.startswith('ticket-'):
            await interaction.response.send_message(
                "❌ Este botón solo puede usarse en canales de ticket!",
                ephemeral=True
            )
            return

        user = interaction.user
        channel = interaction.channel
        can_close = False

        if f'-{user.name.lower()}-{user.discriminator}' in channel.name:
            can_close = True

        if not can_close:
            config = await load_config()
            guild_id_str = str(channel.guild.id)
            server_config = config.get('servers', {}).get(guild_id_str, {})
            staff_role_ids = server_config.get('staff_role_ids', [])
            for role_id in staff_role_ids:
                if discord.utils.get(user.roles, id=role_id):
                    can_close = True
                    break

        if not can_close and channel.permissions_for(user).manage_channels:
            can_close = True

        if not can_close:
            await interaction.response.send_message(
                "❌ No tienes permiso para cerrar este ticket!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🔒 Cerrando Ticket",
            description="Este ticket se cerrará en 5 segundos...",
            color=0xff0000
        )
        embed.set_footer(text=f"Cerrado por {user.display_name}", icon_url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

        ticket_creator = None
        
        # Primero intentar obtener el creador del topic del canal (más confiable)
        if channel.topic and 'Support ticket for' in channel.topic:
            try:
                # El topic tiene el formato: "Support ticket for DisplayName (user_id)"
                import re
                user_id_match = re.search(r'\((\d+)\)$', channel.topic)
                if user_id_match:
                    user_id = int(user_id_match.group(1))
                    ticket_creator = channel.guild.get_member(user_id)
                    if ticket_creator:
                        logger.info(f"Creador del ticket encontrado por topic: {ticket_creator} (ID: {user_id})")
            except Exception as e:
                logger.error(f"Error extrayendo user_id del topic: {e}")
        
        # Si no se pudo encontrar por topic, intentar por el nombre del canal (método anterior)
        if not ticket_creator:
            parts = channel.name.split('-')
            if len(parts) >= 3:
                username = '-'.join(parts[1:-1])
                discriminator = parts[-1]
                for member in channel.guild.members:
                    if member.name.lower() == username and member.discriminator == discriminator:
                        ticket_creator = member
                        logger.info(f"Creador del ticket encontrado por nombre: {ticket_creator}")
                        break
        
        # Si aún no se encuentra, buscar en los permisos del canal
        if not ticket_creator:
            for overwrite_target, overwrite in channel.overwrites.items():
                if isinstance(overwrite_target, discord.Member):
                    # Si el usuario tiene permisos específicos y no es el bot
                    if (overwrite.view_channel is True and 
                        overwrite.send_messages is True and 
                        overwrite_target != channel.guild.me):
                        ticket_creator = overwrite_target
                        logger.info(f"Creador del ticket encontrado por permisos: {ticket_creator}")
                        break

        # Logging adicional para debugging
        if not ticket_creator:
            logger.warning(f"No se pudo identificar el creador del ticket {channel.name}. Topic: {channel.topic}")
            logger.warning(f"Overwrites del canal: {[(str(target), overwrite.pair()) for target, overwrite in channel.overwrites.items()]}")
        else:
            logger.info(f"Creador del ticket identificado exitosamente: {ticket_creator} para canal {channel.name}")

        try:
            if ticket_creator:
                transcript_content = await create_transcript(channel, ticket_creator)

                import io
                
                # Configuración del servidor
                config = await load_config()
                guild_id_str = str(channel.guild.id)
                server_config = config.get('servers', {}).get(guild_id_str, {})

                # Enviar transcript al canal configurado (si existe)
                transcript_channel_id = server_config.get('transcript_channel_id')
                if transcript_channel_id:
                    transcript_channel = channel.guild.get_channel(transcript_channel_id)
                    if transcript_channel:
                        try:
                            transcript_file = io.StringIO(transcript_content)
                            file = discord.File(transcript_file, filename=f"transcript-{channel.name}.txt")
                            transcript_embed = discord.Embed(
                                title="📝 Transcript del Ticket",
                                description=(
                                    f"**Canal:** {channel.name}\n"
                                    f"**Usuario:** {ticket_creator.display_name}\n"
                                    f"**Cerrado por:** {user.display_name}\n"
                                    f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                ),
                                color=0x3498db
                            )
                            await transcript_channel.send(embed=transcript_embed, file=file)
                            logger.info(f"Transcript enviado al canal {transcript_channel.name} para ticket {channel.name}")
                        except Exception as e:
                            logger.error(f"Error enviando transcript al canal: {e}")

                # SIEMPRE enviar transcript por DM al usuario que creó el ticket
                try:
                    transcript_file_dm = io.StringIO(transcript_content)
                    file_dm = discord.File(transcript_file_dm, filename=f"transcript-{channel.name}.txt")
                    dm_embed = discord.Embed(
                        title="📝 Transcript de tu Ticket",
                        description=(
                            f"Tu ticket en **{channel.guild.name}** ha sido cerrado.\n\n"
                            f"**Canal:** {channel.name}\n"
                            f"**Cerrado por:** {user.display_name}\n"
                            f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                            "Aquí tienes el transcript completo de la conversación."
                        ),
                        color=0x3498db
                    )
                    dm_embed.set_footer(text=f"Servidor: {channel.guild.name}")
                    await ticket_creator.send(embed=dm_embed, file=file_dm)
                    logger.info(f"Transcript enviado por DM a {ticket_creator} ({ticket_creator.id})")
                except discord.Forbidden:
                    logger.warning(f"No se pudo enviar transcript DM a {ticket_creator} - DMs deshabilitados")
                    # Intentar notificar en un canal público si los DMs están deshabilitados
                    try:
                        if transcript_channel_id:
                            transcript_channel = channel.guild.get_channel(transcript_channel_id)
                            if transcript_channel:
                                await transcript_channel.send(
                                    f"⚠️ **Aviso:** No se pudo enviar el transcript por DM a {ticket_creator.mention} "
                                    f"(DMs deshabilitados). El transcript está disponible arriba."
                                )
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"Error enviando transcript DM a {ticket_creator}: {e}")

        except Exception as e:
            logger.error(f"Error creando transcript: {e}")
            # Intentar notificar al usuario del error
            try:
                error_embed = discord.Embed(
                    title="❌ Error con Transcript",
                    description=(
                        f"Hubo un error al generar el transcript de tu ticket.\n"
                        f"Por favor contacta a un administrador si necesitas el historial."
                    ),
                    color=0xff0000
                )
                await ticket_creator.send(embed=error_embed)
            except Exception:
                pass

        await asyncio.sleep(5)

        try:
            await channel.delete(reason=f"Ticket cerrado por {user}")
            logger.info(f"Ticket {channel.name} cerrado por {user} ({user.id})")
        except discord.NotFound:
            pass
        except Exception as e:
            logger.error(f"Error cerrando ticket: {e}")

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(TicketView())
        self.bot.add_view(CloseTicketView())

    @app_commands.command(name="ticket-panel", description="Crear un panel de tickets con botón")
    @app_commands.describe(channel="Canal para enviar el panel de tickets (opcional)")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_panel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        if channel is None:
            channel = interaction.channel

        bot_perms = channel.permissions_for(interaction.guild.me)
        if not bot_perms.send_messages or not bot_perms.embed_links:
            await interaction.response.send_message(
                f"❌ No tengo permisos para enviar mensajes o embeds en {channel.mention}!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎫 Sistema de Tickets de Soporte",
            description=(
                "Al abrir un ticket te estas poniendo en contacto con la administración que te responderá en breve, "
                "por favor expón los motivos de tu ticket de manera concisa para que te podamos ayudar mejor.\n\n"
                "**Qué ocurre cuando creas un ticket:**\n"
                "• Se creará un canal privado solo para ti\n"
                "• Solo tú y el staff pueden verlo\n"
                "• Describe tu problema y te ayudaremos\n\n"
                "**Nota importante:** Solo puedes tener un ticket abierto a la vez."
            ),
            color=0x3498db
        )
        embed.set_footer(text="Haz clic en el botón para crear un ticket")

        view = TicketView()

        try:
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(
                f"✅ Panel de tickets creado en {channel.mention}!",
                ephemeral=True
            )
            logger.info(f"Panel de tickets creado por {interaction.user} en {channel.name}")
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ No tengo permiso para enviar mensajes en {channel.mention}!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error creando panel de tickets: {e}")
            await interaction.response.send_message(
                "❌ Ocurrió un error al crear el panel de tickets!",
                ephemeral=True
            )

    @app_commands.command(name="set-ticket-category", description="Establecer categoría para los tickets")
    @app_commands.describe(category="Categoría para los tickets")
    @app_commands.default_permissions(manage_channels=True)
    async def set_ticket_category(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel
    ):
        try:
            config = await load_config()
            guild_id_str = str(interaction.guild.id)
            if 'servers' not in config:
                config['servers'] = {}
            if guild_id_str not in config['servers']:
                config['servers'][guild_id_str] = {}

            config['servers'][guild_id_str]['ticket_category_id'] = category.id
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)
            await interaction.response.send_message(
                f"✅ Categoría de tickets establecida en: {category.name}",
                ephemeral=True
            )
            logger.info(f"Categoría de tickets establecida a {category.name} por {interaction.user}")

        except Exception as e:
            logger.error(f"Error guardando categoría: {e}")
            await interaction.response.send_message(
                "❌ Ocurrió un error al establecer la categoría del ticket!",
                ephemeral=True
            )
    
    @app_commands.command(name="set-staff-role", description="Establecer rol de staff para los tickets")
    @app_commands.describe(role="Rol que tendrá acceso a los tickets y será mencionado al crearlos")
    @app_commands.default_permissions(manage_roles=True)
    async def set_staff_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        """Establecer el rol de staff para los tickets"""
        try:
            config = await load_config()
            guild_id_str = str(interaction.guild.id)
            if 'servers' not in config:
                config['servers'] = {}
            if guild_id_str not in config['servers']:
                config['servers'][guild_id_str] = {}

            # Agregar el rol a la lista de roles de staff
            if 'staff_role_ids' not in config['servers'][guild_id_str]:
                config['servers'][guild_id_str]['staff_role_ids'] = []
            
            if role.id not in config['servers'][guild_id_str]['staff_role_ids']:
                config['servers'][guild_id_str]['staff_role_ids'].append(role.id)
            
            # También establecer como rol de mención de staff
            config['servers'][guild_id_str]['staff_mention_role_id'] = role.id
            
            # Guardar configuración
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            embed = discord.Embed(
                title="✅ Rol de Staff Configurado",
                description=f"El rol {role.mention} ha sido configurado como rol de staff.",
                color=0x00ff00
            )
            embed.add_field(
                name="Permisos otorgados",
                value="• Acceso a todos los tickets\n• Será mencionado al crear tickets\n• Puede cerrar tickets",
                inline=False
            )
            embed.add_field(
                name="Servidor",
                value=interaction.guild.name,
                inline=True
            )
            embed.add_field(
                name="Rol configurado",
                value=role.mention,
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Rol de staff establecido: {role.name} por {interaction.user} en {interaction.guild.name}")

        except Exception as e:
            logger.error(f"Error estableciendo rol de staff: {e}")
            await interaction.response.send_message(
                "❌ Ocurrió un error al establecer el rol de staff!",
                ephemeral=True
            )
    
    @app_commands.command(name="remove-staff-role", description="Remover rol de staff de los tickets")
    @app_commands.describe(role="Rol que se removerá de la lista de staff")
    @app_commands.default_permissions(manage_roles=True)
    async def remove_staff_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        """Remover un rol de la lista de staff"""
        try:
            config = await load_config()
            guild_id_str = str(interaction.guild.id)
            
            if ('servers' not in config or 
                guild_id_str not in config['servers'] or 
                'staff_role_ids' not in config['servers'][guild_id_str]):
                await interaction.response.send_message(
                    "❌ No hay roles de staff configurados en este servidor.",
                    ephemeral=True
                )
                return
            
            staff_roles = config['servers'][guild_id_str]['staff_role_ids']
            
            if role.id not in staff_roles:
                await interaction.response.send_message(
                    f"❌ El rol {role.mention} no está en la lista de staff.",
                    ephemeral=True
                )
                return
            
            # Remover el rol de la lista
            staff_roles.remove(role.id)
            
            # Si era el rol de mención, limpiar esa configuración también
            if config['servers'][guild_id_str].get('staff_mention_role_id') == role.id:
                if staff_roles:  # Si hay otros roles de staff, usar el primero
                    config['servers'][guild_id_str]['staff_mention_role_id'] = staff_roles[0]
                else:  # Si no hay más roles, remover la configuración
                    config['servers'][guild_id_str].pop('staff_mention_role_id', None)
            
            # Guardar configuración
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            embed = discord.Embed(
                title="✅ Rol de Staff Removido",
                description=f"El rol {role.mention} ha sido removido de la lista de staff.",
                color=0x00ff00
            )
            
            if staff_roles:
                remaining_roles = []
                for role_id in staff_roles:
                    staff_role = interaction.guild.get_role(role_id)
                    if staff_role:
                        remaining_roles.append(staff_role.mention)
                
                embed.add_field(
                    name="Roles de staff restantes",
                    value="\n".join(remaining_roles) if remaining_roles else "Ninguno",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Rol de staff removido: {role.name} por {interaction.user} en {interaction.guild.name}")

        except Exception as e:
            logger.error(f"Error removiendo rol de staff: {e}")
            await interaction.response.send_message(
                "❌ Ocurrió un error al remover el rol de staff!",
                ephemeral=True
            )
    
    @app_commands.command(name="list-staff-roles", description="Mostrar los roles de staff configurados")
    @app_commands.default_permissions(manage_roles=True)
    async def list_staff_roles(self, interaction: discord.Interaction):
        """Mostrar la lista de roles de staff configurados"""
        try:
            config = await load_config()
            guild_id_str = str(interaction.guild.id)
            
            embed = discord.Embed(
                title="👥 Roles de Staff - Tickets",
                description=f"Configuración actual para **{interaction.guild.name}**",
                color=0x3498db
            )
            
            if ('servers' not in config or 
                guild_id_str not in config['servers'] or 
                'staff_role_ids' not in config['servers'][guild_id_str] or
                not config['servers'][guild_id_str]['staff_role_ids']):
                embed.add_field(
                    name="Estado",
                    value="🔴 No hay roles de staff configurados",
                    inline=False
                )
                embed.add_field(
                    name="Para configurar",
                    value="Usa `/set-staff-role` para agregar roles de staff",
                    inline=False
                )
            else:
                staff_role_ids = config['servers'][guild_id_str]['staff_role_ids']
                mention_role_id = config['servers'][guild_id_str].get('staff_mention_role_id')
                
                staff_roles_list = []
                for role_id in staff_role_ids:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        mention_indicator = " 🔔" if role_id == mention_role_id else ""
                        staff_roles_list.append(f"{role.mention}{mention_indicator}")
                    else:
                        staff_roles_list.append(f"❌ Rol no encontrado (ID: {role_id})")
                
                embed.add_field(
                    name="🛡️ Roles de Staff",
                    value="\n".join(staff_roles_list) if staff_roles_list else "Ninguno",
                    inline=False
                )
                
                if mention_role_id:
                    mention_role = interaction.guild.get_role(mention_role_id)
                    embed.add_field(
                        name="🔔 Rol de Mención",
                        value=mention_role.mention if mention_role else f"❌ Rol no encontrado (ID: {mention_role_id})",
                        inline=True
                    )
                
                embed.add_field(
                    name="📊 Total de Roles",
                    value=str(len([r for r in staff_roles_list if not r.startswith("❌")])),
                    inline=True
                )
            
            embed.set_footer(text="🔔 = Rol que será mencionado al crear tickets")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error mostrando roles de staff: {e}")
            await interaction.response.send_message(
                "❌ Ocurrió un error al mostrar los roles de staff!",
                ephemeral=True
            )
    
    @app_commands.command(name="set-transcript-channel", description="Establecer canal para transcripts de tickets")
    @app_commands.describe(channel="Canal donde se enviarán los transcripts de tickets cerrados")
    @app_commands.default_permissions(manage_channels=True)
    async def set_transcript_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        """Establecer el canal donde se enviarán los transcripts"""
        try:
            config = await load_config()
            guild_id_str = str(interaction.guild.id)
            if 'servers' not in config:
                config['servers'] = {}
            if guild_id_str not in config['servers']:
                config['servers'][guild_id_str] = {}

            config['servers'][guild_id_str]['transcript_channel_id'] = channel.id
            
            # Guardar configuración
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            embed = discord.Embed(
                title="✅ Canal de Transcripts Configurado",
                description=f"Los transcripts de tickets cerrados se enviarán a {channel.mention}",
                color=0x00ff00
            )
            embed.add_field(
                name="Servidor",
                value=interaction.guild.name,
                inline=True
            )
            embed.add_field(
                name="Canal configurado",
                value=channel.mention,
                inline=True
            )
            embed.add_field(
                name="Funcionalidad",
                value="• Transcripts automáticos al cerrar tickets\n• Copia enviada por DM al usuario\n• Registro completo de conversaciones",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Canal de transcripts establecido: {channel.name} por {interaction.user} en {interaction.guild.name}")

        except Exception as e:
            logger.error(f"Error estableciendo canal de transcripts: {e}")
            await interaction.response.send_message(
                "❌ Ocurrió un error al establecer el canal de transcripts!",
                ephemeral=True
            )
    
    @app_commands.command(name="remove-transcript-channel", description="Desactivar el envío de transcripts")
    @app_commands.default_permissions(manage_channels=True)
    async def remove_transcript_channel(self, interaction: discord.Interaction):
        """Desactivar el sistema de transcripts"""
        try:
            config = await load_config()
            guild_id_str = str(interaction.guild.id)
            
            if ('servers' not in config or 
                guild_id_str not in config['servers'] or 
                'transcript_channel_id' not in config['servers'][guild_id_str]):
                await interaction.response.send_message(
                    "❌ No hay canal de transcripts configurado en este servidor.",
                    ephemeral=True
                )
                return
            
            # Remover la configuración del canal de transcripts
            del config['servers'][guild_id_str]['transcript_channel_id']
            
            # Guardar configuración
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            embed = discord.Embed(
                title="✅ Transcripts Desactivados",
                description="El sistema de transcripts ha sido desactivado para este servidor.",
                color=0x00ff00
            )
            embed.add_field(
                name="Efecto",
                value="• Ya no se enviarán transcripts al cerrar tickets\n• Los usuarios seguirán recibiendo DM con transcript\n• Puedes reactivarlo con `/set-transcript-channel`",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Sistema de transcripts desactivado por {interaction.user} en {interaction.guild.name}")

        except Exception as e:
            logger.error(f"Error desactivando transcripts: {e}")
            await interaction.response.send_message(
                "❌ Ocurrió un error al desactivar los transcripts!",
                ephemeral=True
            )
    
    @app_commands.command(name="transcript-info", description="Mostrar configuración actual de transcripts")
    @app_commands.default_permissions(manage_channels=True)
    async def transcript_info(self, interaction: discord.Interaction):
        """Mostrar información sobre la configuración de transcripts"""
        try:
            config = await load_config()
            guild_id_str = str(interaction.guild.id)
            
            embed = discord.Embed(
                title="📝 Configuración de Transcripts",
                description=f"Estado actual para **{interaction.guild.name}**",
                color=0x3498db
            )
            
            if ('servers' not in config or 
                guild_id_str not in config['servers'] or 
                'transcript_channel_id' not in config['servers'][guild_id_str]):
                embed.add_field(
                    name="Estado",
                    value="🔴 Transcripts desactivados",
                    inline=False
                )
                embed.add_field(
                    name="Para activar",
                    value="Usa `/set-transcript-channel` para configurar un canal",
                    inline=False
                )
                embed.add_field(
                    name="Nota",
                    value="Los usuarios seguirán recibiendo transcripts por DM aunque esté desactivado el canal",
                    inline=False
                )
            else:
                transcript_channel_id = config['servers'][guild_id_str]['transcript_channel_id']
                channel = interaction.guild.get_channel(transcript_channel_id)
                
                embed.add_field(
                    name="Estado",
                    value="🟢 Transcripts activos",
                    inline=True
                )
                embed.add_field(
                    name="Canal configurado",
                    value=channel.mention if channel else f"❌ Canal no encontrado (ID: {transcript_channel_id})",
                    inline=True
                )
                embed.add_field(
                    name="Funcionalidades activas",
                    value="• ✅ Transcripts al canal configurado\n• ✅ Transcripts por DM a usuarios\n• ✅ Registro completo de conversaciones",
                    inline=False
                )
                
                # Verificar permisos del bot en el canal
                if channel:
                    bot_permissions = channel.permissions_for(interaction.guild.me)
                    perms_status = []
                    
                    if bot_permissions.send_messages:
                        perms_status.append("✅ Enviar mensajes")
                    else:
                        perms_status.append("❌ Enviar mensajes")
                    
                    if bot_permissions.attach_files:
                        perms_status.append("✅ Adjuntar archivos")
                    else:
                        perms_status.append("❌ Adjuntar archivos")
                    
                    embed.add_field(
                        name="Permisos del Bot",
                        value="\n".join(perms_status),
                        inline=True
                    )
            
            embed.set_footer(text="Los transcripts incluyen todo el historial de conversación del ticket")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error mostrando info de transcripts: {e}")
            await interaction.response.send_message(
                "❌ Ocurrió un error al mostrar la información de transcripts!",
                ephemeral=True
            )

    @app_commands.command(name="rename-ticket", description="Cambiar el nombre de un ticket")
    @app_commands.describe(new_name="Nuevo nombre para el ticket (sin espacios, usar guiones)")
    async def rename_ticket(
        self,
        interaction: discord.Interaction,
        new_name: str
    ):
        """Cambiar el nombre de un ticket"""
        channel = interaction.channel
        
        # Verificar que estamos en un canal de ticket
        if not channel.name.startswith('ticket-'):
            await interaction.response.send_message(
                "❌ Este comando solo puede usarse en canales de ticket!",
                ephemeral=True
            )
            return
        
        # Verificar permisos
        user = interaction.user
        can_rename = False
        
        # El creador del ticket puede renombrarlo
        if f'-{user.name.lower()}-{user.discriminator}' in channel.name:
            can_rename = True
        
        # Staff roles pueden renombrar tickets
        if not can_rename:
            try:
                config = await load_config()
                guild_id_str = str(channel.guild.id)
                server_config = config.get('servers', {}).get(guild_id_str, {})
                staff_role_ids = server_config.get('staff_role_ids', [])
                for role_id in staff_role_ids:
                    if discord.utils.get(user.roles, id=role_id):
                        can_rename = True
                        break
            except Exception as e:
                logger.error(f"Error verificando roles de staff: {e}")
        
        # Usuarios con permisos de gestionar canales pueden renombrar
        if not can_rename and channel.permissions_for(user).manage_channels:
            can_rename = True
        
        if not can_rename:
            await interaction.response.send_message(
                "❌ No tienes permiso para renombrar este ticket!",
                ephemeral=True
            )
            return
        
        # Validar el nuevo nombre
        new_name = new_name.lower().strip()
        if not new_name:
            await interaction.response.send_message(
                "❌ El nombre del ticket no puede estar vacío!",
                ephemeral=True
            )
            return
        
        # Limpiar el nombre (remover caracteres no permitidos)
        import re
        new_name = re.sub(r'[^a-z0-9\-_]', '', new_name)
        if not new_name:
            await interaction.response.send_message(
                "❌ El nombre del ticket solo puede contener letras, números, guiones y guiones bajos!",
                ephemeral=True
            )
            return
        
        # Construir el nuevo nombre del canal manteniendo la estructura original
        original_parts = channel.name.split('-')
        if len(original_parts) >= 3:
            # Mantener 'ticket-' al inicio y el discriminador al final
            username = '-'.join(original_parts[1:-1])
            discriminator = original_parts[-1]
            new_channel_name = f"ticket-{new_name}-{username}-{discriminator}"
        else:
            # Fallback si el formato no es el esperado
            new_channel_name = f"ticket-{new_name}"
        
        # Verificar que el nuevo nombre no sea demasiado largo (limite de Discord: 100 caracteres)
        if len(new_channel_name) > 100:
            await interaction.response.send_message(
                "❌ El nombre del ticket es demasiado largo! Máximo 100 caracteres en total.",
                ephemeral=True
            )
            return
        
        # Verificar que no existe ya un canal con ese nombre
        existing_channel = discord.utils.get(channel.guild.channels, name=new_channel_name)
        if existing_channel and existing_channel.id != channel.id:
            await interaction.response.send_message(
                f"❌ Ya existe un canal con el nombre `{new_channel_name}`!",
                ephemeral=True
            )
            return
        
        try:
            old_name = channel.name
            await channel.edit(name=new_channel_name, reason=f"Ticket renombrado por {user}")
            
            # Crear embed de confirmación
            embed = discord.Embed(
                title="✅ Ticket Renombrado",
                description=f"El nombre del ticket ha sido cambiado exitosamente.",
                color=0x00ff00
            )
            embed.add_field(
                name="Nombre anterior",
                value=f"`{old_name}`",
                inline=True
            )
            embed.add_field(
                name="Nombre nuevo",
                value=f"`{new_channel_name}`",
                inline=True
            )
            embed.add_field(
                name="Renombrado por",
                value=user.mention,
                inline=False
            )
            embed.set_footer(text=f"Renombrado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"Ticket renombrado de {old_name} a {new_channel_name} por {user} ({user.id})")
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ No tengo permisos para renombrar canales!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error renombrando ticket: {e}")
            await interaction.response.send_message(
                "❌ Ocurrió un error al renombrar el ticket!",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Tickets(bot))
