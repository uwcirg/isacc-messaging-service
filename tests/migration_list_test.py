import pytest
from migrations.utils import Node, LinkedList
from pytest import fixture


@fixture
def linked_list():
    ll = LinkedList()
    ll.add("node1")
    ll.add("node2")
    ll.add("node3")
    ll.add("node4")
    ll.add("node5")
    return ll


def test_node_creation():
    node = Node("data")
    assert node.data == "data"
    assert node.prev_node is None
    assert node.next_node is None


def test_node_equality():
    node1 = Node("data1")
    node2 = Node("data2")
    assert node1 == Node("data1")
    assert node1 != node2


def test_node_hashing():
    node1 = Node("data1")
    node2 = Node("data2")
    node3 = Node("data1")
    assert hash(node1) == hash("data1")
    assert hash(node1) != hash(node2)
    assert hash(node1) == hash(node3)


def test_linked_list_find(linked_list):
    node = linked_list.find("node3")
    assert node.data == "node3"


def test_linked_list_next(linked_list):
    node = linked_list.next("node3")
    assert node.data == "node4"


def test_linked_list_previous(linked_list):
    node = linked_list.previous("node3")
    assert node.data == "node2"


def test_linked_list_get_empty_sublist(linked_list):
    sublist = linked_list.get_sublist(linked_list.get_head().data)
    assert len(sublist) == 0


def test_linked_list_get_sublist(linked_list):
    sublist = linked_list.get_sublist("node2")
    assert sublist == ["node3", "node4", "node5"]


def test_linked_list_add(linked_list):
    linked_list.add("node6")
    assert linked_list.get_head().data == "node6"


def test_linked_list_build_list_from_dictionary():
    previous_nodes = {
        "node1": "None",
        "node2": "node1",
        "node3": "node2",
        "node4": "node3",
        "node5": "node4"
    }
    ll = LinkedList()
    ll.build_list_from_dictionary(previous_nodes)
    assert ll.get_head().data == "node5"
