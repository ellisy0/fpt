import argparse
import configparser
import openai
import os
import re
import datetime
import shutil
import time
from plyer import notification
import platform
import threading

def play_sound(sound_file_path):
    system = platform.system()
    
    if system == 'Windows':
        import winsound
        winsound.PlaySound(sound_file_path, winsound.SND_FILENAME)
    elif system == 'Darwin':
        os.system(f'afplay {sound_file_path}')
    elif system == 'Linux':
        os.system(f'aplay {sound_file_path}')
    else:
        print("Unable to play notification sound: Unsupported platform")

def send_notification(secs_taken, model_name):
    notification.notify(
        title='Request Finished!',
        message='Took {:.2f} seconds. Model: {}'.format(secs_taken, model_name),
        app_name='gpt-cli',
        timeout=10
    )
    play_sound("notification.wav")

# convert a list of strings into messages, including custom prompts
def construct_messages_from_sections(sections):
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "The following messages you will receive contain **Markdown formatting**, and you can reply to them using Markdown formatting, like links, tables, bold, italics, code blocks, inline latex, etc. You can highlight the key words with **bold**, render the math formulas using inline $euqations$, and use markdown tables to show suitable information. Reply with 'understood' to continue."},
        {"role": "assistant", "content": "Understood. I'm ready to proceed with your questions and messages in Markdown formatting."},
        ]
    for i, section in enumerate(sections):
        if i % 2 == 0:
            messages.append({"role": "user", "content": section})
        else:
            messages.append({"role": "assistant", "content": section})
    return messages

# send messages to GPT and return the response
def sendToGPT(messages, is_gpt_4):
    global args
    if is_gpt_4:
        model = "gpt-4"
        price_rate = 0.03
    else:
        model = "gpt-3.5-turbo"
        price_rate = 0.002
    start_time = time.time()
    if args.verbose:
        print("Verbose: sending request using {}, messages = {}".format(model, messages))
    response = openai.ChatCompletion.create(model=model, messages = messages)
    text = response["choices"][0]["message"]["content"]
    prompt_tokens = response["usage"]["prompt_tokens"]
    completion_tokens = response["usage"]["completion_tokens"]
    total_tokens = response["usage"]["total_tokens"]
    end_time = time.time()
    spent_cents = total_tokens * price_rate / 10
    if args.verbose or config.getboolean('Options', 'show_tokens'):
        print("[gpt-cli] Request finished. Model: {}, took {:.2f} seconds. Used tokens: {} ({} prompt + {} response). Calculated cost: {:.2f} cents".format(model, end_time - start_time, total_tokens, prompt_tokens, completion_tokens, spent_cents))
    if config.getboolean('Options', 'notifications'):
        notification_thread = threading.Thread(target=send_notification, args=(end_time - start_time, model))
        notification_thread.start()
    return text, prompt_tokens, completion_tokens, total_tokens

# function to insert "> " in front of each line in a string (markdown blockquote)
def insert_gt(string):
    lines = string.splitlines()
    for i in range(len(lines)):
        lines[i] = "> " + lines[i]
    return "\n".join(lines)

# check if a string is a markdown blockquote
def is_md_blockquote(s):
    for line in s.split('\n'):
        if not line.startswith('> '):
            return False
    return True

# delete the first two characters of each line in a string
def delete_first_two_chars(string):
    lines = string.split('\n')
    for i in range(len(lines)):
        lines[i] = lines[i][2:]
    new_string = '\n'.join(lines)
    return new_string

# remove the markdown blockquote formatting from a string
def remove_md_blockquote_if_present(string):
    if is_md_blockquote(string):
        return delete_first_two_chars(string)
    else:
        return string

# add markdown blockquote formatting to a string
def add_md_blockquote_if_not_present(string):
    if is_md_blockquote(string):
        return string
    else:
        return insert_gt(string)

# handle the formatting at end of the file
def reformat_end_of_file(file):
    with open(file, 'r') as f:
        content = f.read()
    if content.isspace() or content == '':
        content = ''
        with open(file, 'w') as f:
            f.write(content)
    elif re.search(r'\n\n----\n*$', content):
        content = re.sub(r'\n\n----\n*$', '\n\n----\n\n', content)
        with open(file, 'w') as f:
            f.write(content)
    else:
        content = re.sub(r'\n*$', '\n\n----\n\n', content, 1)
        with open(file, 'w') as f:
            f.write(content)

# append a message to the end of a file
def append_message_to_file(message, file, type):
    # type is either 'prompt' or 'response'
    if type == 'prompt':
        message = insert_gt(message)
    elif type != 'response':
        print('Error: type must be either prompt or response when using append_message_to_file.')
        exit()
    reformat_end_of_file(file)
    # append the message to the end of the file
    with open(file, 'a') as f:
        f.write(message + '\n\n----\n\n')

# remove the last message from a file
def remove_last_message_from_file(file):
    with open(file, 'r') as f:
        content = f.read()
    sections = content.split('\n\n----\n\n')
    if len(sections) <= 2 or sections[-1] != '':
        print("Something's wrong at remove_last_message_from_file. You win! Open an issue on GitHub.")
    else:
        sections = sections[:-2]
        content = '\n\n----\n\n'.join(sections)
        with open(file, 'w') as f:
            f.write(content + '\n\n----\n\n')

# assuming the format is correct, and the last message is a prompt, blockquote the last message
def blockquote_last_message(file):
    with open(file, 'r') as f:
        content = f.read()
    sections = content.split('\n\n----\n\n')
    if len(sections) == 1 or sections[-1] != '':
        print("Something's wrong at blockquote_last_message. You win! Open an issue on GitHub.")
    else:
        sections[-2] = add_md_blockquote_if_not_present(sections[-2])
        content = '\n\n----\n\n'.join(sections)
        with open(file, 'w') as f:
            f.write(content)

# for new files, blockquote the prompt and add a horizontal rule
def blockquote_file(file):
    with open(file, 'r') as f:
        content = f.read()
    content = add_md_blockquote_if_not_present(content)
    with open(file, 'w') as f:
        f.write(content + '\n\n----\n\n')

def append_to_file(file, content):
    with open(file, 'a') as f:
        f.write(content)

def prepend_to_file(file, content):
    with open(file, 'r+') as f:
        original_content = f.read()
        f.seek(0, 0)
        f.write(content + original_content)

# returns a tuple (type, messages), mixed use for optimization
# 1. check if a file is a previously saved thread, or conforms to the format of a saved thread
# types can be "plain", "vaild_ends_with_prompt", "valid_ends_with_response", "invalid_ordering"
# 2. if the file is valid, return the list of messages, otherwise return an empty list
# also reformats the file
def file_type_check_get_messages(file):
    reformat_end_of_file(file)
    with open(file, 'r') as f:
        content = f.read()
    if re.search(r'\n\n----\n\n', content):
        sections = content.split('\n\n----\n\n')
        if sections[-1] == '' or sections[-1].isspace():
            sections.pop()
        if len(sections) == 1:
            blockquote_last_message(file)
            return "plain", [remove_md_blockquote_if_present(sections[0])]
        for i, section in enumerate(sections[:-1]):
            if i % 2 == 0:
                if not is_md_blockquote(section):
                    return "invalid_ordering", []
                sections[i] = delete_first_two_chars(section)
            else:
                if is_md_blockquote(section):
                    return "invalid_ordering", []
        if len(sections) % 2 == 0:
            if is_md_blockquote(sections[-1]):
                return "invalid_ordering", []
            else:
                return "valid_ends_with_response", sections
        else:
            sections[-1] = remove_md_blockquote_if_present(sections[-1])
            blockquote_last_message(file)
            return "valid_ends_with_prompt", sections
    else:
        blockquote_file(file)
        return "plain", [remove_md_blockquote_if_present(content)]

# generate a filename for a new thread
def generate_filename(archive_directory):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    files = os.listdir(archive_directory)
    todays_files = [file for file in files if file.startswith(today)]
    used_numbers = [int(file.split('-')[-1].split('.')[0][2:]) for file in todays_files]
    # Find the first available sequential number up to three digits
    for number in range(1, 1000):
        if number not in used_numbers:
            seq_number = f"{number:02d}"
            break
    new_filename = f"{today}-ai{seq_number}.md"
    return new_filename

# interactive mode
def interactive_mode():
    global usage_history_file
    global args
    while True:
        print('Type the next question or command, h for help: ', end='')
        user_input = input()
        if user_input == 'h':
            print('f: read next question from file. f3 to force GPT-3.5, f4 to force GPT-4')
            print('r: re-generate the last response. r3 to force GPT-3.5, r4 to force GPT-4')
            print('o: read the file and respond to the last one question only. o3 to force GPT-3.5, o4 to force GPT-4.')
            print('d: dump-to-history (clear the current file and archive the cleared thread into history file)')
            print('df: dump-to-file (clear the current file and archive the cleared thread into a new file in the archive directory, with a generated file name)')
            print('q: quit the program')
            print('h: print this help message')
        elif user_input == 'f' or user_input == 'f3' or user_input == 'f4':
            if user_input == 'f3':
                is_gpt_4 = False
            elif user_input == 'f4':
                is_gpt_4 = True
            else:
                is_gpt_4 = args.gpt4
            type, sections = file_type_check_get_messages(args.file)
            if type == "invalid_ordering":
                print('Invalid ordering in the file. Please check the file and try again.')
            elif type == "valid_ends_with_response":
                print('The file ends with a response. Please ask a question at the end of thread.')
            else:
                messages = construct_messages_from_sections(sections)
                response, _, _, _ = sendToGPT(messages, is_gpt_4)
                append_message_to_file(response, args.file, 'response')
        elif user_input == 'r' or user_input == 'r3' or user_input == 'r4':
            if user_input == 'r3':
                is_gpt_4 = False
            elif user_input == 'r4':
                is_gpt_4 = True
            else:
                is_gpt_4 = args.gpt4
            remove_last_message_from_file(args.file)
            type, sections = file_type_check_get_messages(args.file)
            if type == "invalid_ordering":
                print('Invalid ordering in the file. Please check the file and try again.')
            elif type == "valid_ends_with_response":
                print('The file ends with a response. This shouldn\'t happen...')
            else:
                messages = construct_messages_from_sections(sections)
                response, _, _, _ = sendToGPT(messages, is_gpt_4)
                append_message_to_file(response, args.file, 'response')
        elif user_input == 'o' or user_input == 'o3' or user_input == 'o4':
            if user_input == 'o3':
                is_gpt_4 = False
            elif user_input == 'o4':
                is_gpt_4 = True
            else:
                is_gpt_4 = args.gpt4
            type, sections = file_type_check_get_messages(args.file)
            if type == "invalid_ordering":
                print('Invalid ordering in the file. Please check the file and try again.')
            elif type == "valid_ends_with_response":
                print('The file ends with a response. Please ask a question at the end of thread.')
            else:
                messages = construct_messages_from_sections([sections[-1]])
                response, _, _, _ = sendToGPT(messages, is_gpt_4)
                append_message_to_file(response, args.file, 'response')
        elif user_input == 'd' or user_input == 'df':
            if user_input == 'd':
                target_file = usage_history_file
                with open(args.file, 'r') as f:
                    content = f.read()
                if prepend_history:
                    prepend_to_file(target_file, content)
                else:
                    append_to_file(target_file, content)
            else:
                target_file = generate_filename(archive_directory)
                target_file = os.path.join(archive_directory, target_file)
                shutil.copy(args.file, target_file)
            with open(args.file, 'w') as f:
                f.write('')
            print('Cleared the current file and archived the cleared thread to {}.'.format(target_file))
        elif user_input == 'q':
            print('Quitting the program...')
            exit()
        else:
            type, sections = file_type_check_get_messages(args.file)
            if type == "invalid_ordering":
                print('Invalid ordering in the file. Please check the file and try again.')
            elif type == "valid_ends_with_prompt":
                print('The file ends with a prompt. Please use \'f\' if you want to continue the thread.')
            elif type == "plain":
                print('No thread detected. Please use \'f\' if you want to start a thread from the content in the file.')
            else:
                append_message_to_file(user_input, args.file, 'prompt')
                sections.append(user_input)
                messages = construct_messages_from_sections(sections)
                response, _, _, _ = sendToGPT(messages, args.gpt4)
                append_message_to_file(response, args.file, 'response')

# parse the command line arguments
parser = argparse.ArgumentParser(
    prog='fpt',
    description='A CLI for OpenAI\'s GPT-3.5/GPT-4 API',
)
input_group = parser.add_mutually_exclusive_group(required=True)
input_group.add_argument('-f', '--file', type=str, help='The file to operate on')
input_group.add_argument('-q', '--question', type=str, help='A single question to send to GPT')
parser.add_argument('-4', '--gpt4', action='store_true', help='Use GPT-4')
parser.add_argument('-v', '--verbose', action='store_true', help='Verbose mode')
args = parser.parse_args()

# turn file path into absolute path
if args.file:
    args.file = os.path.abspath(args.file)

# set current working directory to the directory of this script
os.chdir(os.path.dirname(os.path.realpath(__file__)))

# read the config file
config = configparser.ConfigParser()
config.read('fpt.conf')
if config.has_option('OpenAI', 'custom_api_base'):
    openai.api_base = config.get('OpenAI', 'custom_api_base')
    api_key = config.get('OpenAI', 'custom_api_key')
else:
    api_key = config.get('OpenAI', 'api_key')
archive_directory = config.get('Directories', 'archive_directory')
usage_history_file = config.get('Directories', 'usage_history_file')
prepend_history = config.getboolean('Options', 'prepend_history')

# set the API key
openai.api_key = api_key

# create the archive directory and usage history file if they don't exist
if not os.path.exists(archive_directory):
    os.makedirs(archive_directory)
if not os.path.exists(usage_history_file):
    open(usage_history_file, 'a').close()

# if the user asked a single question, answer it, save the response, and exit
if args.question:
    messages = construct_messages_from_sections([args.question])
    response, _, _, _ = sendToGPT(messages, is_gpt_4=args.gpt4)
    print(response)
    content_to_write = add_md_blockquote_if_not_present(args.question) + '\n\n----\n\n' + response + '\n\n----\n\n'
    if prepend_history:
        prepend_to_file(usage_history_file, content_to_write)
    else:
        append_to_file(usage_history_file, content_to_write)

# if the user asked to operate on a file, enter interactive mode
elif args.file:
    if not os.path.isfile(args.file):
        print('Error: file does not exist. Exiting...')
        exit()
    type, sections = file_type_check_get_messages(args.file)
    if type == 'invalid_ordering':
        print('Error: invalid ordering of messages. Make sure there are alternating prompts and responses. Exiting...')
        exit()
    elif type == 'valid_ends_with_response':
        print('File ends with a response. Entering interactive mode...')
        interactive_mode()
    elif type == 'valid_ends_with_prompt' or type == 'plain':
        messages = construct_messages_from_sections(sections)
        response, _, _, _ = sendToGPT(messages, is_gpt_4=args.gpt4)
        append_message_to_file(response, args.file, 'response')
        interactive_mode()
    else:
        print('Error: invalid file type. Exiting...')
        exit()
