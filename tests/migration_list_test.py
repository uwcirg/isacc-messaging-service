import pytest
from pytest import fixture
from migrations.utils import LinkedList


@fixture
def linked_list():
    return LinkedList()


def test_append(linked_list):
    linked_list.append("A")
    linked_list.append("B")
    linked_list.append("C")
    assert linked_list.get_head().data == "A"
    assert linked_list.get_head().next_node.data == "B"
    assert linked_list.get_head().next_node.next_node.data == "C"


def test_find(linked_list):
    linked_list.append("A")
    linked_list.append("B")
    linked_list.append("C")
    assert linked_list.find("B").data == "B"
    assert linked_list.find("D") is None


def test_get_previous_node(linked_list):
    linked_list.append("A")
    linked_list.append("B")
    linked_list.append("C")
    assert linked_list.get_previous_node("C") == "B"
    assert linked_list.get_previous_node("A") is None


def test_get_sublist(linked_list):
    linked_list.append("A")
    linked_list.append("B")
    linked_list.append("C")
    linked_list.append("D")
    assert linked_list.get_sublist("B", "D") == ["C", "D"]
    assert linked_list.get_sublist("A") == ["B", "C", "D"]


def test_check_for_cycles(linked_list):
    linked_list.append("A")
    linked_list.append("B")
    linked_list.append("C")
    linked_list.append("D")
    assert linked_list.check_for_cycles() == False

    # Introduce a cycle
    linked_list.find("D").prev_node = linked_list.find("A")
    assert linked_list.check_for_cycles() == True
