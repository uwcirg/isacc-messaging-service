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

    def find(self, data) -> Node:
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

    def build_list_from_array(self, migration_nodes: dict):
        # Second, link each node to its previous node
        for migration, node in migration_nodes.items():
            prev_node_id = migration_nodes[migration]
            if prev_node_id:
                prev_node = Node(prev_node_id) if not self.find(prev_node_id) else self.find(prev_node_id)
                # If there is a previous node, link it to the current node
                node.prev_node = prev_node
                # Link the previous node to the current node as its next node
                prev_node.next_node = node

        # Find the node that has no 'next_node' (i.e., the tail node)
        for node in migration_nodes.values():
            if node.next_node is None:
                self.set_head(node)
                break
    
        # If no tail node exists and length is not zero, means there is a circual dependency, no outgoing edges
        if self.head == None:
            error_message = "Cycle detected in the list"
            raise ValueError(error_message)

    def set_head(self, new_head):
        """Set the head node."""
        self.head = new_head

    def get_head(self):
        """Get the head node."""
        return self.head

    def display(self):
        """Display all of the nodes"""
        current_node = self.head
        while current_node:
            print(current_node)
            current_node = current_node.next_node

    def check_for_cycles(self):
        """Check whether there exists any cycles within the list."""
        if not self.head:
            print("THINKS IT IS FALSE")
            return True

        slow = self.head
        fast = self.head
        while fast and fast.prev_node:
            print(f"{fast} and {fast.prev_node}")
            slow = slow.prev_node
            fast = fast.prev_node.prev_node

            if slow == fast:
                return True

        return False
