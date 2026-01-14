import os, json, subprocess
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from queue import all_jobs

def run(cmd):
    return subprocess.getoutput(cmd)
