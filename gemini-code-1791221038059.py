# ============================================================
# BOT MÉDICO - WhatsApp | App de produção (Railway)
# Junta tudo que foi construído no Colab num único serviço
# que fica sempre no ar, com link fixo.
# ============================================================

import os
import json
import sqlite3
from datetime import datetime, timedelta

import requests
from flask import Flask, request, render_template_string

# ------------------------------------------------------------
# CONFIGURAÇÃO — no Railway, defina isso em Variables
# ------------------------------------------------------------
DB_PATH = os.environ.get("DB_PATH", "clinica.db")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "troque_esta_palavra_secreta")
TELEFONE_PLANTAO_CLINICA = os.environ.get("TELEFONE_PLANTAO_CLINICA", "")
GRAPH_API_URL = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"

DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]


# ------------------------------------------------------------
# Banco de dados
# ------------------------------------------------------------
def conectar():
    return sqlite3.connect(DB_PATH)

def criar_tabelas():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS medicos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
        especialidade TEXT NOT NULL, ativo INTEGER DEFAULT 1)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS horarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT, medico_id INTEGER NOT NULL,
        dia_semana INTEGER NOT NULL, hora_inicio TEXT NOT NULL, hora_fim TEXT NOT NULL,
        duracao_consulta_min INTEGER DEFAULT 30,
        FOREIGN KEY (medico_id) REFERENCES medicos(id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS pacientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, cpf TEXT UNIQUE NOT NULL,
        telefone_whatsapp TEXT, criado_em TEXT DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS convenios (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cpf TEXT NOT NULL, nome_plano TEXT NOT NULL,
        status TEXT DEFAULT 'ativo', validade TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS agendamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, paciente_id INTEGER NOT NULL, medico_id INTEGER NOT NULL,
        data TEXT NOT NULL, hora TEXT NOT NULL, tipo TEXT DEFAULT 'normal',
        status TEXT DEFAULT 'confirmado', criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (paciente_id) REFERENCES pacientes(id), FOREIGN KEY (medico_id) REFERENCES medicos(id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS conversas (
        telefone TEXT PRIMARY KEY, estado TEXT NOT NULL, dados_temp TEXT DEFAULT '{}',
        atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()
    conn.close()

def adicionar_medico(nome, especialidade):
    conn = conectar(); cur = conn.cursor()
    cur.execute("INSERT INTO medicos (nome, especialidade) VALUES (?, ?)", (nome, especialidade))
    conn.commit(); medico_id = cur.lastrowid; conn.close()
    return medico_id

def adicionar_horario(medico_id, dia_semana, hora_inicio, hora_fim, duracao_consulta_min=30):
    conn = conectar(); cur = conn.cursor()
    cur.execute("""INSERT INTO horarios (medico_id, dia_semana, hora_inicio, hora_fim, duracao_consulta_min)
                   VALUES (?, ?, ?, ?, ?)""", (medico_id, dia_semana, hora_inicio, hora_fim, duracao_consulta_min))
    conn.commit(); conn.close()

def listar_medicos_por_especialidade(especialidade):
    conn = conectar(); cur = conn.cursor()
    cur.execute("SELECT id, nome FROM medicos WHERE especialidade = ? AND ativo = 1", (especialidade,))
    resultado = cur.fetchall(); conn.close()
    return resultado

def cadastrar_ou_atualizar_paciente(cpf, nome=None, telefone_whatsapp=None):
    conn = conectar(); cur = conn.cursor()
    cur.execute("SELECT id FROM pacientes WHERE cpf = ?", (cpf,))
    existente = cur.fetchone()
    if existente:
        paciente_id = existente[0]
        if nome or telefone_whatsapp:
            cur.execute("""UPDATE pacientes SET nome = COALESCE(?, nome),
                           telefone_whatsapp = COALESCE(?, telefone_whatsapp) WHERE id = ?""",
                        (nome, telefone_whatsapp, paciente_id))
    else:
        cur.execute("INSERT INTO pacientes (cpf, nome, telefone_whatsapp) VALUES (?, ?, ?)",
                     (cpf