import discord
from discord.ext import commands
from discord import app_commands
import json
import logging
from typing import Optional
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def create_transcript(channel: discord.TextChannel, user: discord.User) -> str:
    """Create a transcript of the ticket channel"""
    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        author = f"{message.author.display_name} ({message.author.name}#{message.author.discriminator})"
        content = message.content or "[No content]"
        
        # Handle embeds
        if message.embeds:
            for embed in message.embeds:
                if embed.title:
                    content += f"\n[Embed: {embed.title}]"
                if embed.description:
                    content += f"\n{embed.description}"
        
        # Handle attachments
        if message.attachments:
            for attachment in message.attachments:
                content += f"\n[Attachment: {attachment.filename}]"
        
        messages.append(f"[{timestamp}] {author}: {content}")
    
    transcript = f"Transcript del Ticket: {channel.name}\n"
    transcript += f"Usuario: {user.display_name} ({user.name}#{user.discriminator})\n"
    transcript += f"Creado: {channel.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
    transcript += f"Cerrado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    transcript += "=" * 50 + "\n\n"
    transcript += "\n".join(messages)
    
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
        
        # Check if user already has a ticket
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
            # Load config
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            # Get category for tickets
            category = None
            if config.get('ticket_category_id'):
                category = guild.get_channel(config['ticket_category_id'])
            
            # Set up permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_channels=True,
                    manage_messages=True
                )
            }
            
            # Add staff roles to permissions
            for role_id in config.get('staff_role_ids', []):
                role = guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        manage_messages=True
                    )
            
            # Create ticket channel
            ticket_channel = await guild.create_text_channel(
                name=f'ticket-{user.name.lower()}-{user.discriminator}',
                category=category,
                overwrites=overwrites,
                topic=f'Support ticket for {user.display_name} ({user.id})'
            )
            
            # Create close ticket view
            close_view = CloseTicketView()
            
            # Send welcome message in ticket
            embed = discord.Embed(
                title="🎫 Ticket de Soporte Creado",
                description=f"¡Hola {user.mention}! Gracias por crear un ticket.\n\n"
                           f"Por favor describe tu problema en detalle y nuestro staff te ayudará en breve.\n\n"
                           f"Para cerrar este ticket, haz clic en el botón de abajo.",
                color=0x00ff00
            )
            embed.set_footer(text=f"Ticket creado por {user.display_name}", icon_url=user.display_avatar.url)
            
            # Mention staff role in ticket
            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
                staff_mention_role_id = 1020374565207150626
                staff_role = guild.get_role(staff_mention_role_id)
                if staff_role:
                    await ticket_channel.send(f"{staff_role.mention} - Nuevo ticket creado por {user.mention}")
            except:
                pass
            
            await ticket_channel.send(embed=embed, view=close_view)
            
            await interaction.followup.send(
                f"✅ Tu ticket ha sido creado: {ticket_channel.mention}",
                ephemeral=True
            )
            
            logger.info(f"Ticket created by {user} ({user.id}) in {guild.name}")
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ No tengo permisos para crear canales!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            await interaction.followup.send(
                "❌ Ocurrió un error al crear tu ticket!",
                ephemeral=True
            )

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
                "❌ This button can only be used in ticket channels!",
                ephemeral=True
            )
            return
        
        # Check if user has permission to close ticket
        user = interaction.user
        channel = interaction.channel
        
        # Allow ticket creator or staff to close
        can_close = False
        
        # Check if user is ticket creator
        if f'-{user.name.lower()}-{user.discriminator}' in channel.name:
            can_close = True
        
        # Check if user has staff role
        if not can_close:
            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
                
                for role_id in config.get('staff_role_ids', []):
                    if user.get_role(role_id):
                        can_close = True
                        break
            except:
                pass
        
        # Check if user has manage channels permission
        if not can_close and channel.permissions_for(user).manage_channels:
            can_close = True
        
        if not can_close:
            await interaction.response.send_message(
                "❌ You don't have permission to close this ticket!",
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
        
        # Get ticket creator from channel name
        ticket_creator = None
        parts = channel.name.split('-')
        if len(parts) >= 3:
            username = '-'.join(parts[1:-1])
            discriminator = parts[-1]
            for member in channel.guild.members:
                if member.name.lower() == username and member.discriminator == discriminator:
                    ticket_creator = member
                    break
        
        # Create transcript
        try:
            if ticket_creator:
                transcript_content = await create_transcript(channel, ticket_creator)
                
                # Save transcript to file
                import io
                transcript_file = io.StringIO(transcript_content)
                file = discord.File(transcript_file, filename=f"transcript-{channel.name}.txt")
                
                # Send to transcript channel
                transcript_channel_id = 1175492699156127866
                transcript_channel = channel.guild.get_channel(transcript_channel_id)
                if transcript_channel:
                    transcript_embed = discord.Embed(
                        title="📝 Transcript del Ticket",
                        description=f"**Canal:** {channel.name}\n"
                                   f"**Usuario:** {ticket_creator.display_name}\n"
                                   f"**Cerrado por:** {user.display_name}\n"
                                   f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        color=0x3498db
                    )
                    await transcript_channel.send(embed=transcript_embed, file=file)
                
                # Send transcript to ticket creator via DM
                try:
                    transcript_file_dm = io.StringIO(transcript_content)
                    file_dm = discord.File(transcript_file_dm, filename=f"transcript-{channel.name}.txt")
                    dm_embed = discord.Embed(
                        title="📝 Transcript de tu Ticket",
                        description=f"Tu ticket en **{channel.guild.name}** ha sido cerrado.\n"
                                   f"Aquí tienes el transcript completo de la conversación.",
                        color=0x3498db
                    )
                    await ticket_creator.send(embed=dm_embed, file=file_dm)
                except discord.Forbidden:
                    logger.info(f"Could not send transcript DM to {ticket_creator} - DMs disabled")
                except Exception as e:
                    logger.error(f"Error sending transcript DM: {e}")
                    
        except Exception as e:
            logger.error(f"Error creating transcript: {e}")
        
        # Wait 5 seconds then delete channel
        await asyncio.sleep(5)
        
        try:
            await channel.delete(reason=f"Ticket closed by {user}")
            logger.info(f"Ticket {channel.name} closed by {user} ({user.id})")
        except discord.NotFound:
            pass  # Channel already deleted
        except Exception as e:
            logger.error(f"Error closing ticket: {e}")

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Add persistent views
        self.bot.add_view(TicketView())
        self.bot.add_view(CloseTicketView())
    
    @app_commands.command(name="ticket-panel", description="Create a ticket panel with button")
    @app_commands.describe(
        channel="Channel to send the ticket panel (optional, defaults to current channel)"
    )
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_panel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        if channel is None:
            channel = interaction.channel
        
        # Check bot permissions in target channel
        bot_perms = channel.permissions_for(interaction.guild.me)
        if not bot_perms.send_messages or not bot_perms.embed_links:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages or embed links in {channel.mention}!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🎫 Sistema de Tickets de Soporte",
            description="Al abrir un ticket te estas poniendo en contacto con la administracion que te respondera en breve, porfavor expon los motivos de tu ticket de manera concisa para que te podamos ayudar mejor.\n\n"
                       "**Qué ocurre cuando creas un ticket:**\n"
                       "• Se creará un canal privado solo para ti\n"
                       "• Solo tú y el staff pueden verlo\n"
                       "• Describe tu problema y te ayudaremos\n\n"
                       "**Nota importante:** Solo puedes tener un ticket abierto a la vez.",
            color=0x3498db
        )
        embed.set_footer(text="Haz clic en el botón para crear un ticket")
        
        view = TicketView()
        
        try:
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(
                f"✅ Ticket panel created in {channel.mention}!",
                ephemeral=True
            )
            logger.info(f"Ticket panel created by {interaction.user} in {channel.name}")
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {channel.mention}!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error creating ticket panel: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while creating the ticket panel!",
                ephemeral=True
            )
    
    @app_commands.command(name="set-ticket-category", description="Set the category for ticket channels")
    @app_commands.describe(category="Category channel for tickets")
    @app_commands.default_permissions(manage_channels=True)
    async def set_ticket_category(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel
    ):
        try:
            # Load and update config
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            config['ticket_category_id'] = category.id
            
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            await interaction.response.send_message(
                f"✅ Ticket category set to: {category.name}",
                ephemeral=True
            )
            logger.info(f"Ticket category set to {category.name} by {interaction.user}")
            
        except Exception as e:
            logger.error(f"Error setting ticket category: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while setting the ticket category!",
                ephemeral=True
            )
    
    @app_commands.command(name="add-staff-role", description="Add a staff role for ticket access")
    @app_commands.describe(role="Role to add as staff")
    @app_commands.default_permissions(manage_roles=True)
    async def add_staff_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        try:
            # Load and update config
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            if 'staff_role_ids' not in config:
                config['staff_role_ids'] = []
            
            if role.id not in config['staff_role_ids']:
                config['staff_role_ids'].append(role.id)
                
                with open('config.json', 'w') as f:
                    json.dump(config, f, indent=2)
                
                await interaction.response.send_message(
                    f"✅ Added {role.mention} as a staff role for tickets!",
                    ephemeral=True
                )
                logger.info(f"Staff role {role.name} added by {interaction.user}")
            else:
                await interaction.response.send_message(
                    f"❌ {role.mention} is already a staff role!",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error adding staff role: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while adding the staff role!",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Tickets(bot))
