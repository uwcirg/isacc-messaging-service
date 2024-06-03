"""Double Linked-List

Defines a specialized doubly linked list implementation restricted to unique data 
values and no cycles to prevent migration conflicts. Holds no cycles and raises
errors when duplicate values are attempted to be added. Is intended to be re-build
each time new migration is added to the migrations directory. 

Self.head is always pointing to the latest created migration id, tail is pointing
to the first created migration (the migration with no preceding migration).
Hence, primary iterates backwards and adds forward.
"""
class Node:
    def __init__(self, data):
        """Initialize a node with two connections containing data."""
        self.data = data
        self.prev_node = None
        self.next_node = None

    def __repr__(self):
        """Representation of the node."""
        return f"{self.data}"

    def __eq__(self, other):
        """Check equality of nodes."""
        if isinstance(other, Node):
            return self.data == other.data
        return False

    def __hash__(self):
        """Hash the node's data."""
        return hash(self.data)


class LinkedList:
    def __init__(self):
        """Initialize a linked list."""        
        self.head = None

    def __contains__(self, data):
        """Find whether specific data is present in the list."""
        current_node = self.head
        while current_node:
            if current_node.data == data:
                return True
            current_node = current_node.prev_node
        return False

    def find(self, data) -> Node:
        """Find the first node containing specified data."""
        current_node = self.head
        while current_node:
            if current_node.data == data:
                return current_node
            current_node = current_node.prev_node
        return None

    def next_node(self, current_node_data) -> Node:
        """Retrieve node after the specified one."""
        next_node = self.head
        while next_node and next_node.prev_node:
            if next_node.prev_node.data == current_node_data:
                return next_node
            next_node = next_node.prev_node
        return None

    def next(self, current_node_data) -> object:
        """Retrieve data from the node after the specified one."""
        node = self.next_node(current_node_data)
        if node:
            return node.data
        else:
            return None

    def previous_node(self, current_node_data) -> Node:
        """Retrieve node before the specified one."""
        current_node = self.find(current_node_data)
        if current_node and current_node.prev_node:
            return current_node.prev_node
        return None
    
    def previous(self, current_node_data) -> object:
        """Retrieve data from the node before the specified one."""
        node = self.previous_node(current_node_data)
        if node:
            return node.data
        else:
            return None
    
    def get_sublist(self, first_node_data: str, last_node_data: str = None) -> list:
        """Return a list consisting of nodes between the specified boundaries.
        Inclusive of last endpoint, but not of first."""
        unapplied_migrations = []
        if last_node_data is None:
            last_node = self.head
        else:
            last_node = self.find(last_node_data)

        # Iterate over migrations starting from the latest migration
        while last_node and last_node.data != first_node_data:
            unapplied_migrations.append(last_node.data)
            last_node = last_node.prev_node

        # Reverse to account for the order
        unapplied_migrations.reverse()

        return unapplied_migrations

    def add(self, data):
        """Add new node after the head, updating the head.
        Raises an error if node with such migration already exists in the list."""
        new_node = self.find(data)
        if new_node:
            raise ValueError("adding a duplicate item")
        new_node = Node(data)

        if self.head is None:
            self.head = new_node
        else:
            current_node = self.head
            current_node.next_node = new_node
            new_node.prev_node = current_node
            self.head = new_node

    def build_list_from_dictionary(self, previous_nodes: dict):
        '''Creates a sorted LinkedList where head is the latest created migration in the directory.
        Tail is the migration pointing to "None," all new migrations are added after the head'''
        nodes_references: dict = {}
        for key in previous_nodes.keys():
            node = Node(key)
            nodes_references[key] = node

        # First, create all migration nodes without linking them
        for migration, node in nodes_references.items():
            prev_node_id = previous_nodes[migration]
            if prev_node_id != 'None':
                prev_node = nodes_references[prev_node_id]
                if prev_node:
                    node.prev_node = prev_node
                    prev_node.next_node = node

        # Find the migration node that has no 'next_node' (i.e., the tail node)
        for node in nodes_references.values():
            if node.next_node is None:
                self.head = node
                break

        # Assess whether there are any inconsistencies
        self.check_consistency()

    def check_consistency(self):
        '''Iterates from the head to check whether all of the nodes were rightly assigned 
        prev and next node references'''
        
        # If no tail node exists and length is not zero, means there is a circular dependency, no outgoing edges
        if self.head == None:
            error_message = "Cycle detected in the sequence"
            raise RuntimeError(error_message)

        node = self.head

        while node:
            if node.next_node is None and node != self.head:
                raise RuntimeError(f"Consistency error: find a node without a next reference that is not the head")

            # Check for inconsistent references
            if node.next_node:
                next_node = self.find(node.next_node.data)
                if next_node.prev_node != node:
                    raise RuntimeError("Consistency error: node references are not consistent")
            if node.prev_node:
                prev_node = self.find(node.prev_node.data)
                if prev_node.next_node != node:
                    raise RuntimeError("Consistency error: node references are not consistent")
            node = node.prev_node

        return True

    def check_dictionary_consistency(self, nodes_references: dict):
            '''Iterates over the dictionary to check whether all of the nodes were rightly assigned 
            prev and next node references'''
            
            # If no tail node exists and length is not zero, means there is a circular dependency, no outgoing edges
            if self.head == None:
                error_message = "Cycle detected in the list"
                raise ValueError(error_message)

            tail_count = 0

            for node in nodes_references.values():
                if node.next_node is None and node != self.head:
                    raise RuntimeError(f"Consistency error: find a node without a next reference that is not the head")
                elif node.prev_node is None:
                    tail_count += 1

                # Check for inconsistent references
                if node.next_node:
                    next_node = self.find(node.next_node.data)
                    if next_node.prev_node != node:
                        raise RuntimeError(f"Consistency error: node references are not consistent")
                if node.prev_node:
                    prev_node = self.find(node.prev_node.data)
                    if prev_node.next_node != node:
                        raise RuntimeError(f"Consistency error: node references are not consistent")

            if tail_count != 1:
                raise RuntimeError(f"Consistency error: expected exactly one tail node, found {tail_count}")

            return True
