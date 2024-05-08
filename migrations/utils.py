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

    def __hash__(self):
        return hash(self.data)


class LinkedList:
    def __init__(self):
        self.head = None

    def find(self, data) -> Node:
        """Find the first node containing the specified data."""
        # Traverse forward
        current_node = self.head
        while current_node:
            if current_node.data == data:
                return current_node
            current_node = current_node.next_node

        # If not found, start from the tail node
        current_node = self.head
        while current_node:
            if current_node.data == data:
                return current_node
            current_node = current_node.prev_node

        # If not found, return None
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
        Inclusive of last endpoint."""
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

    def add(self, data):
        """Add node after the head."""
        new_node = self.find(data)
        if new_node:
            
        else:
            new_node = Node(data)

            if self.head is None:
                self.head = new_node
            else:
                current_node = self.head
                while current_node.next_node:
                    current_node = current_node.next_node
                current_node.next_node = new_node
                new_node.prev_node = current_node
                self.head = new_node

    def build_list_from_dictionary(self, previous_nodes: dict):
        nodes_references: dict = {}
        # Make sure we are working with Nodes
        for key in previous_nodes.keys():
            node = Node(key)
            nodes_references[key] = node

        # First, create all migration nodes without linking them
        for migration, node in nodes_references.items():
            prev_node_id = previous_nodes[migration]
            if prev_node_id != 'None':
                prev_node = nodes_references[prev_node_id]
                if prev_node:
                    # If there is a previous migration, link it to the current node
                    node.prev_node = prev_node
                    # Link the previous node to the current node as its next node
                    prev_node.next_node = node

        # Find the migration node that has no 'next_node' (i.e., the tail node)
        for node in nodes_references.values():
            if node.next_node is None:
                self.head = node
                break

        # If no tail node exists and length is not zero, means there is a circual dependency, no outgoing edges
        if self.head == None:
            error_message = "Cycle detected in the list"
            raise ValueError(error_message)

    def get_head(self):
        """Get the head node."""
        return self.head
