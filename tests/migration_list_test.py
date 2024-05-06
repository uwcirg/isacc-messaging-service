import pytest
from migrations.utils import Node, LinkedList

@pytest.fixture
def linked_list():
    return LinkedList()

def test_linked_list_operations(linked_list):
    # Create nodes
    node_a = Node("A")
    node_b = Node("B")
    node_c = Node("C")

    # Test append
    linked_list.append(node_a)
    linked_list.append(node_b)
    linked_list.append(node_c)

    # Test prepend
    linked_list.prepend(Node("D"))
    assert linked_list.head.data == "D"

    # Test insert
    linked_list.insert("D", Node("E"))
    assert linked_list.head.next_node.data == "E"

    # Test find
    found_node = linked_list.find("B")
    assert found_node == node_b

    # Test get_following_node
    following_node = linked_list.get_following_node("C")
    assert following_node.data == "B"

    # Test get_previous_node
    previous_node = linked_list.get_previous_node("E")
    assert previous_node.data == "D"

    # Test get_sublist
    sublist = linked_list.get_sublist("D", "B")
    assert sublist == ["E", "D"]

    # Test update_head
    linked_list.update_head("C")
    assert linked_list.head.data == "C"

    # Test set_head
    linked_list.set_head(node_a)
    assert linked_list.head == node_a

    # Test get_head
    head = linked_list.get_head()
    assert head == node_a

    # Test reverse
    linked_list.reverse()
    assert linked_list.head.data == "C"

    # Test display
    linked_list.display()  # Simply check if it runs without errors

    # Test check_for_cycles
    assert not linked_list.check_for_cycles()

    # Create cycle
    node_c.next_node = node_a
    assert linked_list.check_for_cycles()
