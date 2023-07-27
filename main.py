import discord
import os
import datetime
import openai
import tiktoken
import re

TOKEN = os.getenv("DISCORD_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

client = discord.Client(intents=discord.Intents.all())
os.makedirs('./output', exist_ok=True)
model=input("Use GPT-4 instead of GPT-3.5 (y/N): ")

forbidden_channels = []
async def fetch_messages(channel, after):
    message_list = []

    try:
        messages = channel.history(after=after)
        async for message in messages:
            if not message.content:
                continue
            message_list.append(f"[{message.created_at.strftime('%Y-%m-%d %H:%M')}] {message.author}: {message.content}\n")
        if message_list:
            print(f"Fetched messages from {channel.guild.name} / {channel.name}")
            filename = re.sub(r'[\\/:"*?<>|]', '', channel.name)
            with open(f'./output/{filename}.txt', 'a') as f:
                for msg in message_list:
                    f.write(msg)
    except discord.Forbidden:
        forbidden_channels.append(f"{channel.name}")
        # print(f"Bot doesn't have the required permissions to fetch messages from {channel.guild.name} / {channel.name}")

def user_input_guild(guilds):
    print("\nWhich guild would you like to search?")
    for i, guild in enumerate(guilds, 1):
        print(f"{i}. {guild.name}")
    choice = input("\nEnter the number of your choice: ")
    return guilds[int(choice) - 1]

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    guild = user_input_guild(client.guilds)
    days = int(input("How many days of history would you like to fetch? "))
    after = datetime.datetime.now() - datetime.timedelta(days=days)
    print("")

    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            await fetch_messages(channel, after)

    active_threads = await guild.active_threads()
    for thread in active_threads:
        if isinstance(thread, discord.Thread):
            await fetch_messages(thread, after)
    print(f"Could not access the following channels: {', '.join(forbidden_channels)}.")
    print("Finished checking all available channels.\n")
    await client.close()

def summarize(model="gpt-4", max_tokens=8192):
    tokenizer = tiktoken.get_encoding("cl100k_base")
    token_count = 0

    system_prompt = f"You are a Discord message summarizer, providing clear and concise markdown summaries of today's messages in the JuiceboxDAO Discord server. JuiceboxDAO builds Juicebox, an Ethereum funding protocol. Today's date is {datetime.date.today().strftime('%B %d, %Y')}. Please start with a summary that briefly outlines the most important topics discussed. Following this, write markdown sections with summaries for each significant topic. Within these sections, I would like bullet points summarizing the most important points raised, and inline or block quotes from any particularly important messages. Omit spam and discussions pertaining to blatant promotion."
    token_count += len(tokenizer.encode(system_prompt))

    all_messages = ''
    skipped_files = []
    for filename in os.listdir('./output'):
        if filename.endswith('.txt'):
            with open(os.path.join('./output', filename), 'r') as readfile:
                message = f'\n=== Content from {filename} ===\n' + readfile.read()
                message_tokens = len(tokenizer.encode(message))
                if token_count + message_tokens < max_tokens:
                    print(f"Added {filename} to context.")
                    all_messages += message
                    token_count += message_tokens
                else:
                    skipped_files.append(filename)
                    continue
    if skipped_files:
        print(f"Skipped: {', '.join(skipped_files)}.")

    
    response = openai.ChatCompletion.create(
        model=model,
        stream=True,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": all_messages}
        ]
    )

    print("\n")
    with open("summary.md", "w") as file:
        for chunk in response:
            content = chunk["choices"][0]["delta"].get("content", "") # pyright: ignore
            if content is not None:
                print(content, end="", flush=True)
                file.write(content)
    print("\n\nSummary written to summary.md")


if TOKEN and openai.api_key:
    client.run(TOKEN)
    if model.lower()=="y":
        summarize("gpt-4", 7192) # 8192 max
    else:
        summarize("gpt-3.5-turbo-16k", 15384) # 16384 max
else:
    print("Missing $DISCORD_TOKEN or $OPENAI_API_KEY environmental variable.")
