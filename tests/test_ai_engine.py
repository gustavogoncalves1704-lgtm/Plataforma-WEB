"""Testes unitários para os schemas Pydantic do motor de IA."""
import pytest
from modules.ai_engine import ChecklistItem, AnaliseProduto, ParecerTecnico

class TestChecklistItem:
    def test_criacao_valida(self):
        item = ChecklistItem(
            requisito="Tensão 220V",
            atendido=True,
            observacao="Produto suporta 110V e 220V",
        )
        assert item.requisito == "Tensão 220V"
        assert item.atendido is True

    def test_observacao_padrao(self):
        item = ChecklistItem(requisito="Potência mínima 1500W", atendido=False)
        assert item.observacao == ""

class TestAnaliseProduto:
    def test_criacao_completa(self):
        checklist = [
            ChecklistItem(requisito="Tensão 220V", atendido=True),
            ChecklistItem(requisito="Potência 1500W", atendido=True),
        ]
        analise = AnaliseProduto(
            marca="Britânia",
            modelo="Turbo Force 2000",
            conforme=True,
            checklist=checklist,
            porcentagem_conformidade=100.0,
        )
        assert analise.conforme is True
        assert len(analise.checklist) == 2

    def test_conformidade_parcial(self):
        checklist = [
            ChecklistItem(requisito="Tensão 220V", atendido=True),
            ChecklistItem(requisito="Potência 1500W", atendido=False),
        ]
        analise = AnaliseProduto(
            marca="Cadence",
            modelo="XPTO",
            conforme=False,
            checklist=checklist,
            porcentagem_conformidade=50.0,
        )
        assert analise.conforme is False

class TestParecerTecnico:
    def test_parecer_favoravel(self):
        parecer = ParecerTecnico(
            resumo="Análise técnica concluída",
            produtos_recomendados=["Britânia Turbo Force"],
            justificativa="Todos os requisitos atendidos",
            parecer_conclusivo="FAVORÁVEL à aquisição",
        )
        assert "FAVORÁVEL" in parecer.parecer_conclusivo
        assert len(parecer.produtos_recomendados) == 1
        assert parecer.produtos_rejeitados == []