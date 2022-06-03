## parts from here: https://gist.github.com/Rapptz/c4324f17a80c94776832430007ad40e6#slash-commands-and-context-menu-commands

from discord.app_commands import Choice
from discord.ext import tasks, commands
import discord
import asyncio
import os
import re
import subprocess
import time
import datetime
from dotenv import load_dotenv
from typing import Optional
import sqlite3
import logging


from discord_promptschool import * #including client and tree

HOME_DIR="/home/yak/robot/promptschool/"
USER_DIR="/home/yak/"
LISTOFTABLES=['prompts','hints','courses','responses'] #no hint support yet

load_dotenv(USER_DIR+'.env')

conn=sqlite3.connect(HOME_DIR+'promptschooldatabase.db')  
db_c = conn.cursor()

class standardrecord:
#based on db_c.execute('''CREATE TABLE {0} (seq INTEGER PRIMARY KEY, id int, creatorid text, contents text, filled int, createdat int, filledat int, parentid int, mlink text, other text)'''.format(tab)) 
    def __init__(self):
        self.seq=None
        self.id=0 #id of teh item, usually provided by discord
        self.creatorid=0 #user id of creator
        self.contents="" #the actual payload
        self.filled=0 #some sort of marking
        self.createdat=0 #when was it created
        self.filledat=0 #when was it marked
        self.parentid=0 # one level up in hierarchy
        self.mlink="" #some link data. not used
        self.other="" #some other data. not used

    def set(self, rawrecord):
        self.seq=rawrecord[0] #just a running count
        self.id=rawrecord[1] #id of teh item, usually provided by discord
        self.creatorid=rawrecord[2] #user id of creator
        self.contents=rawrecord[3] #the actual payload
        self.filled=rawrecord[4] #soem sort of marking
        self.createdat=rawrecord[5] #when was it created
        self.filledat=rawrecord[6] #when was it marked
        self.parentid=rawrecord[7] # one level up in hierarchy
        self.mlink=rawrecord[8] #some link data. not used
        self.other=rawrecord[9] #some other data. not used
        return (self)
    def totuple(self):
        return(self.seq, self.id, self.creatorid,self.contents,self.filled,self.createdat,self.filledat,self.parentid,self.mlink,self.other)

def putrecord(tab, rec):
    rec.createdat=int(time.time())
    rec.seq=None
    db_c.execute('''insert into {} values    (?,?,?,?,?,?,?,?,?,?)'''.format(tab),rec.totuple())
    conn.commit()
    return rec
def getonerecord(tab, id):
    one=standardrecord()
    res=db_c.execute('select * from {} where id=? order by seq desc'.format(tab),(id,)).fetchone() #before we only returned contents.
    print(id,res)
    if not res:
        return None
    return one.set(res)
def getallrecords(tab, id):
    rows=db_c.execute('select * from {} where id=? order by seq desc'.format(tab),(id,)).fetchall()
    man=[]
    for r in rows:
        one=standardrecord()
        one.set(r)
        man.append(one)
    return(man)
def getqallrecords(tab, id=None,parentid=None,creatorid=None):
    wstr="1"
    if id:
        wstr=wstr+" and id="+str(id)
    if parentid:
        wstr=wstr+" and parentid="+str(parentid)
    if creatorid:
        wstr=wstr+" and creatorid="+str(creatorid)
    
    rows= db_c.execute('select * from {0} where {1} order by seq desc'.format(tab,wstr)).fetchall()
    man=[]
    for r in rows:
        one=standardrecord()
        one.set(r)
        man.append(one)
    return(man)
def getqonerecord(tab, id=None,parentid=None,creatorid=None):
    wstr="1"
    if id:
        wstr=wstr+" and id="+str(id)
    if parentid:
        wstr=wstr+" and parentid="+str(parentid)
    if creatorid:
        wstr=wstr+" and creatorid="+str(creatorid)
    one=standardrecord()
    return one.set(db_c.execute('select * from {0} where {1} order by seq desc'.format(tab,wstr)).fetchone())




class pscourse(app_commands.Group):#commands: create, set, show, showall, recall, recallall. no del yet
    @app_commands.command(name="create",description="create a new course")
    @app_commands.describe(name="a short name of the course, will become channel name")
    async def course_create(self,interaction:discord.Interaction,name:str):
        #create legal name - lest see what happens without
        #do not care if it already exists.
        #create channel with name name under PROMPTSCHOOL_CATEGORY_ID
        category=await client.guilds[0].fetch_channel(PROMPTSCHOOL_CATEGORY_ID)
        channel=await client.guilds[0].create_text_channel(name,category=category)
        #create record with the data parentID=PROMPTSCHOOL_CATEGORY_ID
        one=standardrecord()
        one.parentid=PROMPTSCHOOL_CATEGORY_ID
        one.id=channel.id
        one.creatorid=interaction.user.id
        one.contents="no description provided yet. use /pscourse set command"
        putrecord("courses",one)
        await interaction.response.send_message("created course {} in the prompt school category".format(name), ephemeral=True)
        return
        
    @app_commands.command(name="registerthischannel",description="(advanced) turn this existing channel, wherever it is, into a prompt course")
    async def course_register(self,interaction:discord.Interaction):
        #allows to register existing ongoing courseseven if not under PROMPTSCHOOL_CATEGORY_ID
        one=standardrecord()
        one.parentid=PROMPTSCHOOL_CATEGORY_ID #even if not actually there
        one.id=interaction.channel.id
        one.creatorid=interaction.user.id
        one.contents="no description provided yet. use `/pscourse set` command"
        putrecord("courses",one)
        await interaction.response.send_message("this channel is now a course managerd by /psXXX promptschool bot. new prompts will be in threads. use /pshelp to learn more", ephemeral=False)
        return

    @app_commands.command(name="set",description="set course topic")
    @app_commands.describe(topic="a description of what the course is about")
    async def course_set(self,interaction:discord.Interaction,topic:str):
        cur_chan_id=interaction.channel.id
        one=getonerecord("courses",cur_chan_id)
        if not one:
            await interaction.response.send_message("you need to run set from within the course channel", ephemeral=True)
            return

        cur_chan=await client.guilds[0].fetch_channel(cur_chan_id)
        #physically update the channel topic
        await cur_chan.edit(topic=topic)
        #update record with the data 
        one.contents=topic
        one.creatorid=interaction.user.id
        putrecord("courses",one)
        await interaction.response.send_message("updated course topic", ephemeral=True)
        return

    @app_commands.command(name="recall",description="show course topic, private")
    async def course_recall(self,interaction:discord.Interaction):
        cur_chan_id=interaction.channel.id
        one=getonerecord("courses",cur_chan_id)
        if not one:
            await interaction.response.send_message("you need to run recall from within the course channel", ephemeral=True)
            return
        await interaction.response.send_message("course topic is:\n{}".format(one.contents), ephemeral=True)
        return

    @app_commands.command(name="show",description="show course topic")
    async def course_show(self,interaction:discord.Interaction):
        cur_chan_id=interaction.channel.id
        one=getonerecord("courses",cur_chan_id)
        if not one:
            await interaction.response.send_message("you need to run show from within the course channel", ephemeral=True)
            return
        await interaction.response.send_message("course topic is:\n{}".format(one.contents), ephemeral=False)
        return

class psprompt(app_commands.Group):
    @app_commands.command(name="create",description="create a new prompt and a thread for discussing the prompt")
    @app_commands.describe(name="a short name of the prompt, will become thread name")
    async def prompt_create(self,interaction:discord.Interaction,name:str):
        cur_chan_id=interaction.channel.id
        one=getonerecord("courses",cur_chan_id)
        if not one:
            await interaction.response.send_message("you need to create thread from within a course channel", ephemeral=True)
            return
        #do not care if it already exists.
        #create thread with name name under current channel
        channel=await client.guilds[0].fetch_channel(cur_chan_id)
        tempmess=await channel.send("now opening a new prompt thread {}".format(name))
        thread=await channel.create_thread(name=name, message=tempmess)
        #create record with the data parentID=cur_chan_id
        one=standardrecord()
        one.parentid=cur_chan_id
        one.id=thread.id
        one.creatorid=interaction.user.id
        one.contents="no prompt body provided yet. use /psprompt set command"
        putrecord("prompts",one)
        await interaction.response.send_message("created prompt-thread {} in this channel".format(name), ephemeral=True)
        return



    @app_commands.command(name="set",description="set prompt contents")
    @app_commands.describe(theprompt="the contents of the prompt, markdown allowed.")
    async def prompt_set(self,interaction:discord.Interaction,theprompt:str):
        cur_chan_id=interaction.channel.id
        one=getonerecord("prompts",cur_chan_id)
        if not one:
            await interaction.response.send_message("you need to run set from within a prompt-thread", ephemeral=True)
            return

        #in future pin a message with the prompt
        one.contents=theprompt
        one.creatorid=interaction.user.id
        putrecord("prompts",one)
        await interaction.response.send_message("updated prompt contents", ephemeral=True)
        await splitsend(interaction.channel,"new prompt set for channel:\n"+theprompt,False)
        return

    @app_commands.command(name="recall",description="show prompt topic, private")
    async def prompt_recall(self,interaction:discord.Interaction):
        cur_chan_id=interaction.channel.id
        one=getonerecord("prompts",cur_chan_id)
        if not one:
            await interaction.response.send_message("you need to run recall from within a prompt-thread", ephemeral=True)
            return
        await interaction.response.send_message("the prompt by <@{0}>is:\n{1}".format(one.creatorid,one.contents), ephemeral=True)
        return

    @app_commands.command(name="show",description="show course topic")
    async def prompt_show(self,interaction:discord.Interaction):
        cur_chan_id=interaction.channel.id
        one=getonerecord("prompts",cur_chan_id)
        if not one:
            await interaction.response.send_message("you need to run show from within a prompt-thread", ephemeral=True)
            return
        await interaction.response.send_message("the prompt by <@{0}>is:\n{1}".format(one.creatorid,one.contents), ephemeral=False)
        return

    @app_commands.command(name="reaction",description="give feedback on the prompt")
    @app_commands.describe(reaction="choose how you feel about the prompt")
    @app_commands.describe(words="explain using words, if you want")
    @app_commands.choices(reaction=[
    Choice(name='good', value=1),
    Choice(name='too hard', value=2),
    Choice(name='too easy', value=3),
    Choice(name='scary',value=4),
    Choice(name='didnt know what to do', value=5),])
    async def prompt_reaction(self,interaction:discord.Interaction, reaction: Choice[int], words: Optional[str]):
        cur_chan_id=interaction.channel.id
        one=getonerecord("prompts",cur_chan_id)
        if not one:
            await interaction.response.send_message("you need to run show from within a prompt-thread", ephemeral=True)
            return
        print("reaction:",reaction,reaction.name)
        print("words:",words)
        if not words:
            words=""
        await interaction.response.send_message("this information is not yet being saved:\n"+reaction.name+" "+words, ephemeral=True)
        return


class psresponse(app_commands.Group):
    @app_commands.command(name="submit",description="create and submit a response to the prompt")
    @app_commands.describe(theresponse="your response to the prompt, can be text or a link or both. files not supported, yet")
    async def response_submit(self,interaction:discord.Interaction,theresponse:str):
        cur_chan_id=interaction.channel.id
        one=getonerecord("prompts",cur_chan_id)
        if not one:
            await interaction.response.send_message("you need to send response from within a prompt-thread ", ephemeral=True)
            return
        #do not care if it already exists.

        one=standardrecord()
        one.parentid=cur_chan_id
        one.id=int(time.time()) #just need a number, this has no real meaning as we search by creator and thread id
        one.creatorid=interaction.user.id
        one.contents=theresponse
        putrecord("responses",one)
        await interaction.response.send_message("submitted response. do you want to share? /psresponse show. want to edit? /psresponse submit again.", ephemeral=True)
        return


    @app_commands.command(name="recall",description="show submission, private")
    async def response_recall(self,interaction:discord.Interaction):
        cur_chan_id=interaction.channel.id
        one=getqonerecord("responses",parentid=cur_chan_id,creatorid=interaction.user.id)
        if not one:
            await interaction.response.send_message("failure to retrieve. you need to run recall from within a prompt-thread or you have not yet submitted a response", ephemeral=True)
            return
        await interaction.response.send_message("the response by <@{0}>is:\n{1}".format(one.creatorid,one.contents), ephemeral=True)
        return

    @app_commands.command(name="show",description="show submission, publicly")
    async def response_show(self,interaction:discord.Interaction):
        cur_chan_id=interaction.channel.id
        one=getqonerecord("responses",parentid=cur_chan_id,creatorid=interaction.user.id)
        if not one:
            await interaction.response.send_message("failure to retrieve. you need to run recall from within a prompt-thread or you have not yet submitted a response", ephemeral=True)
            return
        await interaction.response.send_message("the response by <@{0}>is:\n{1}".format(one.creatorid,one.contents), ephemeral=False)
        return

class pshint(app_commands.Group):
    @app_commands.command(name="submit",description="create and submit a hint for the prompt")
    @app_commands.describe(thehint="a hint that can help people complete teh prompt, can be text or a link or both. files not supported, yet")
    async def hint_submit(self,interaction:discord.Interaction,thehint:str):
        cur_chan_id=interaction.channel.id
        one=getonerecord("prompts",cur_chan_id)
        if not one:
            await interaction.response.send_message("you need to submit a hint from within a prompt-thread ", ephemeral=True)
            return
        #do not care if it already exists.

        one=standardrecord()
        one.parentid=cur_chan_id
        one.id=int(time.time()) #just need a number, this has no real meaning as we search by creator and thread id
        one.creatorid=interaction.user.id
        one.contents=thehint
        putrecord("hints",one)
        await interaction.response.send_message("submitted hint. to share /pshint show.  to edit? /pshint submit again.", ephemeral=True)
        return


    @app_commands.command(name="recall",description="show hint, private, for now only one")
    async def hint_recall(self,interaction:discord.Interaction):
        cur_chan_id=interaction.channel.id
        one=getqonerecord("hints",parentid=cur_chan_id,creatorid=interaction.user.id)
        if not one:
            await interaction.response.send_message("failure to retrieve. you need to run recall from within a prompt-thread or you there is no hint available", ephemeral=True)
            return
        await interaction.response.send_message("the hint by <@{0}>is:\n{1}".format(one.creatorid,one.contents), ephemeral=True)
        return

    @app_commands.command(name="show",description="show latest hint, publicly")
    async def hint_show(self,interaction:discord.Interaction):
        cur_chan_id=interaction.channel.id
        one=getqonerecord("hints",parentid=cur_chan_id,creatorid=interaction.user.id)
        if not one:
            await interaction.response.send_message("failure to retrieve. you need to run show from within a prompt-thread or you there is no hint available", ephemeral=True)
            return
        await interaction.response.send_message("the hint by <@{0}>is:\n{1}".format(one.creatorid,one.contents), ephemeral=False)
        return


#class pshelp(app_commands.Group): #lets try a command before we try a group
#    @app_commands.command(name="HELP", description="how to use the /ps promptschool system")
@tree.command(name="pshelp",description="how to use the /ps promptschool system")
async def pshelp(interaction:discord.Interaction):
    hm='''
**Basic concept**:
(i) all courses are under the catagory "prompt school", each in its own channel
(ii) each prompt has its own thread under teh course channel
(iii) updating does not delete old data, just adds new data - like a blockchain
**Example**:
`/pscourse create a new course` - creates a new course channel called "a-new-course"
you now move to that channel (manually)
`/pscourse set this is an experimental course` - sets the description of the course (as the channel topic)
`/psprompt create test prompt` - creates a new thread called "test-prompt" under the channel "a-new-course". this command must be run in the _course channel_, not a thread
you now move to that thread
`/psprompt set a cool prompt` - sets the prompt of this thread to be "a cool prompt". you can change the prompt contents by rerunning this command
`/psprompt recall` - gives you a private showing of the prompt of thsi thread. each thread has its own prompt
`/psprompt show` - public posting of prompt
`/psresponse submit my response` - submits "my response" as your response to the prompt _in this thread_. you can rerun to change the submission
`/psresponse show` or `recall` - shows your response
`/psreaction`  - allows you to give a reaction to the prompt. not yet stored
`/pshint create a great hint` - allows you to add a hint. viewable using `/pshint show` or `recall`
`/pshelp` - shows this or maybe a better message
**to convert existing channels (but not their prompts, at this time)**
`/pscourse registerthischannel` - registers current channel to be a course that /psXXX can manage
    '''
    await interaction.response.send_message(hm, ephemeral=True)
    return
   
#now need commands for stats

#this class maybe we can delete soon
class pstest(app_commands.Group): #not being added anymore?
    @app_commands.command(name="echo")
    @app_commands.describe(txt="the text to echo")
    async def test_echo(self,interaction:discord.Interaction,txt:str):
        await interaction.response.send_message(f'test echo {txt=}', ephemeral=True)
    @app_commands.command(name="doubleecho")
    @app_commands.describe(txt="the text to double echo")
    async def test_double_echo(self,interaction:discord.Interaction,txt:str):
        await interaction.response.send_message(f'test doubleecho {txt=}{txt=}', ephemeral=True)


@client.event #needed since it takes time to connect to discord
async def on_ready(): 
#    tree.copy_global_to(guild=client.guilds[0])
#    m= await tree.sync()
    tree.add_command(pscourse())#need to be added manually for some reason
    tree.add_command(pstest())#need to be added manually for some reason
    tree.add_command(psprompt())#need to be added manually for some reason
    tree.add_command(psresponse())#need to be added manually for some reason
    tree.add_command(pshint())#need to be added manually for some reason
#    tree.add_command(pshelp())#if single command, no need to add
    tree.copy_global_to(guild=client.guilds[0]) #the commands were probably defined as global
    print(client.guilds[0],client.guilds[0].id)
    m= await tree.sync(guild=client.guilds[0])
    print([x.name for x in m])
    if len(m)==0:
        m= await tree.sync(guild=discord.Object(id=MY_GUILD_ID))
        print([x.name for x in m])

    checkon_database()
    print("promptschool is up!")
    print([x.name for x in tree.get_commands()])
    return

async def durl2m(u): #needs to be redone for thread...
    print(u)
    url=u.split("/")
    url=list(reversed(url))
    print(url)
    c=client.guilds[0].get_channel_or_thread(int(url[1]))
    m=await c.fetch_message(int(url[0]))
    return m,url[1],c

def checkon_database(): 
#check if table exists in DB. if not, create it
    for tab in LISTOFTABLES:
        db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name=? ''',(tab,))
        if db_c.fetchone()[0]!=1:
            db_c.execute('''CREATE TABLE {0} (seq INTEGER PRIMARY KEY, id int, creatorid text, contents text, filled int, createdat int, filledat int, parentid int, mlink text, other text)'''.format(tab)) 
            #filled=is it active
            #most items will not be used...
            conn.commit()


async def splitsend(ch,st,codeformat):
#send data in chunks smaller than 2k
#might it have a bug of dropping last space and last line?
    if len(st)<1900: #discord limit is 2k and we want some play)
        if codeformat:
            await ch.send('```'+st+'```')
        else:
            await ch.send(st)
    else:
        x=st.rfind('\n',0,1900)
        if codeformat:
            await ch.send('```'+st[0:x]+'```')
        else:
            await ch.send(st[0:x])
        await splitsend(ch,st[x+1:],codeformat)

discord_token=os.getenv('PROMPTSCHOOL_DISCORD_KEY')
MY_GUILD_ID=os.getenv('THEYAKCOLLECTIVE_DISCORD_ID')
PROMPTSCHOOL_CATEGORY_ID=os.getenv('PROMPTSCHOOL_CATEGORY_ID')
client.run(discord_token) 
