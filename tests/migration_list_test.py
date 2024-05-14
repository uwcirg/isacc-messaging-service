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


@fixture
def nodes_references(linked_list):
    nodes_references = {
        "node5": linked_list.head,
        "node4": linked_list.head.prev_node,
        "node3": linked_list.head.prev_node.prev_node,
        "node2": linked_list.head.prev_node.prev_node.prev_node,
        "node1": linked_list.head.prev_node.prev_node.prev_node.prev_node,
    }
    return nodes_references


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
    next = linked_list.next("node3")
    assert next == "node4"


def test_linked_list_previous(linked_list):
    previous = linked_list.previous("node3")
    assert previous == "node2"


def test_linked_list_get_empty_sublist(linked_list):
    sublist = linked_list.get_sublist(linked_list.head.data)
    assert len(sublist) == 0


def test_linked_list_get_sublist(linked_list):
    sublist = linked_list.get_sublist("node2")
    assert sublist == ["node3", "node4", "node5"]


def test_linked_list_add(linked_list):
    linked_list.add("node6")
    assert linked_list.head.data == "node6"


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
    assert ll.head.data == "node5"


def test_check_consistency_valid(linked_list):
    """Test consistency check with a valid linked list"""
    assert linked_list.check_consistency()


def test_check_consistency_cycle(linked_list):
    """Test consistency check when head is None"""
    linked_list.head.next_node = linked_list.head.prev_node.prev_node
    with pytest.raises(RuntimeError, match="Cycle detected in the sequence"):
        linked_list.check_consistency()


def test_check_consistency_no_next_reference(linked_list):
    """Test consistency check when a node has no next reference and is not the head"""
    linked_list.head.prev_node.prev_node.next_node = None
    with pytest.raises(RuntimeError, match="Consistency error: find a node without a next reference that is not the head"):
        linked_list.check_consistency()


def test_check_consistency_inconsistent_references(linked_list):
    """Test consistency check when node references are not consistent"""
    linked_list.head.prev_node.prev_node.next_node = linked_list.head
    with pytest.raises(RuntimeError, match="Consistency error: node references are not consistent"):
        linked_list.check_consistency()


def test_check_dictionary_consistency_valid(linked_list, nodes_references):
    assert linked_list.check_dictionary_consistency(nodes_references)


def test_check_dictionary_consistency_cycle(linked_list, nodes_references):
    node1 = nodes_references["node1"]

    linked_list.head.next_node = node1  # Creating a cycle

    with pytest.raises(RuntimeError) as exc_info:
        linked_list.check_dictionary_consistency(nodes_references)
    assert str(exc_info.value) == "Cycle detected in the list"


def test_check_dictionary_consistency_missing_reference(linked_list, nodes_references):
    node3 = nodes_references["node3"]

    node3.next_node = None  # Missing next reference

    with pytest.raises(RuntimeError) as exc_info:
        linked_list.check_dictionary_consistency(nodes_references)
    assert str(exc_info.value) == "Consistency error: find a node without a next reference that is not the head"


def test_check_dictionary_consistency_no_tail(linked_list, nodes_references):
    node1 = nodes_references["node1"]

    node1.prev_node = linked_list.head  # Removing the tail

    with pytest.raises(RuntimeError) as exc_info:
        linked_list.check_dictionary_consistency(nodes_references)
    assert str(exc_info.value) == "Consistency error: Expected exactly one tail node, found 0"


def test_check_dictionary_consistency_multiple_tails(linked_list, nodes_references):
    node4 = nodes_references["node4"]

    node4.prev_node = None  # Adding another tail

    with pytest.raises(RuntimeError) as exc_info:
        linked_list.check_dictionary_consistency(nodes_references)
    assert str(exc_info.value) == "Consistency error: Expected exactly one tail node, found 2"


def test_check_dictionary_consistency_inconsistent_next(linked_list, nodes_references):
    node4 = nodes_references["node4"]
    node3 = nodes_references["node3"]
    node2 = nodes_references["node2"]

    node4.prev_node = node3
    node3.next_node = node2

    with pytest.raises(RuntimeError) as exc_info:
        linked_list.check_dictionary_consistency(nodes_references)
    assert str(exc_info.value) == "Consistency error: node references are not consistent"


def test_check_dictionary_consistency_inconsistent_prev(linked_list, nodes_references):
    node4 = nodes_references["node4"]
    node3 = nodes_references["node3"]
    node2 = nodes_references["node2"]

    node4.prev_node = node3
    node3.next_node = node2

    with pytest.raises(RuntimeError) as exc_info:
        linked_list.check_dictionary_consistency(nodes_references)
    assert str(exc_info.value) == "Consistency error: node references are not consistent"
