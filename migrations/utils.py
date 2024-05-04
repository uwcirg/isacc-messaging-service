import os

class Node:
    def __init__(self, data):
        self.data = data
        self.prev_node = None
        self.next_node = None

    def __repr__(self):
        return f"{self.data}"

    def __eq__(self, other):
        if isinstance(other, Node):
            return self.data == other.data
        return False

class LinkedList:
    def __init__(self):
        self.head = None

    def find(self, data):
        """Find the first node containing the specified data."""
        current_node = self.head
        while current_node:
            if current_node.data == data:
                return current_node
            current_node = current_node.prev_node
        return None

    def get_following_node(self, current_node_data) -> Node:
        """Retrieve node following the specified one."""
        next_node = self.head
        while next_node and next_node.prev_node:
            if next_node.prev_node.data == current_node_data:
                return next_node
            next_node = next_node.prev_node
        return None

    def get_previous_node(self, current_node_data) -> Node:
        """Retrieve node before the specified one."""
        current_node = self.find(current_node_data)
        if current_node and current_node.prev_node:
            return current_node.prev_node.data
        return None

    def get_sublist(self, first_node_data: str, last_node_data: str = None) -> list:
        """Return a list consistings of nodes between the specified boundaries.
        Non-inclusive of endpoints."""
        unapplied_migrations = []
        if last_node_data is None:
            last_node = self.head
        else:
            last_node = self.find(last_node_data)

        # Iterate over migrations starting from top
        while last_node and last_node.data != first_node_data:
            unapplied_migrations.append(last_node.data)
            last_node = last_node.prev_node

        # Reverse to account for the order
        unapplied_migrations.reverse()

        return unapplied_migrations

    def update_head(self, current_node = None) -> str:
        """Returns node without an outgoing edge to other node."""
        if not current_node:
            current_node = self.head
        while current_node and current_node.next_node:
            current_node = current_node.next_node
            self.head = current_node

    def append(self, data):
        """Append node after the head."""
        new_node = self.find(data)
        # If do not exist, create the nodes
        new_node = new_node if new_node else Node(data)

        if self.head is None:
            self.head = new_node
        else:
            current_node = self.head
            while current_node.next_node:
                current_node = current_node.next_node
            current_node.next_node = new_node
            new_node.prev_node = current_node
            self.head = new_node

    def prepend(self, data):
        """Prepend node at the tail of the list."""
        new_node = self.find(data)
        # If do not exist, create the nodes
        new_node = new_node if new_node else Node(data)

        if self.head is None:
            self.head = new_node
        else:
            current_node = self.head
            while current_node.prev_node:
                current_node = current_node.prev_node
            current_node.prev_node = new_node
            new_node.next_node = current_node

    def insert(self, prev_node_data:str, curr_node_data: str):
        """Insert node before the curr_node."""
        # Look for the nodes
        prev_node = self.find(prev_node_data) 
        curr_node = self.find(curr_node_data)

        # If do not exist, create the nodes
        prev_node = prev_node if prev_node else Node(prev_node_data)
        curr_node = curr_node if curr_node else Node(curr_node_data)

        if self.head is None:
            self.head = curr_node

        prev_node.next_node = curr_node
        curr_node.prev_node = prev_node

    def set_head(self, new_head):
        """Set the head node."""
        self.head = new_head

    def get_head(self):
        """Get the head node."""
        return self.head

    def reverse(self):
        """Rever the order of the nodes."""
        current_node = self.head
        prev_node = None
        while current_node:
            next_node = current_node.next_node
            current_node.next_node = prev_node
            current_node.prev_node = next_node
            prev_node = current_node
            current_node = next_node
        self.head = prev_node

    def display(self):
        """Display all of the nodes"""
        current_node = self.head
        while current_node:
            print(current_node)
            current_node = current_node.next_node

    def check_for_cycles(self):
        """Check whether there exists any cycles within the list."""
        if not self.head:
            return True

        slow = self.head
        fast = self.head
        while fast and fast.prev_node:
            slow = slow.prev_node
            fast = fast.prev_node.prev_node

            if slow == fast:
                return True

        return False
