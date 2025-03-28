from scripts.protos import keyexchange_pb2, spirc_pb2, player_pb2
from google.protobuf.descriptor import Descriptor, EnumDescriptor

def print_all_fields(proto_module):
    """
    Function to print all fields for all messages in the given protobuf module.
    It will print field names, field types, and labels for each message.
    This version properly checks for Enum types and Message types.
    """
    for message_name in dir(proto_module):
        message_class = getattr(proto_module, message_name)

        # Check if it's a protobuf message (has the 'DESCRIPTOR' and is a Descriptor type)
        if isinstance(getattr(message_class, "DESCRIPTOR", None), Descriptor):
            print(f"=== Inspecting {message_name} Fields ===")
            for field in message_class.DESCRIPTOR.fields:
                field_name = field.name
                field_type = field.type
                field_label = field.label  # OPTIONAL, REQUIRED, REPEATED
                print(f"Field name: {field_name}, Type: {field_type}, Label: {field_label}")
            print("\n")
        elif isinstance(getattr(message_class, "DESCRIPTOR", None), EnumDescriptor):
            # Handle Enum types differently, as they do not have fields
            print(f"Skipping {message_name} (Enum type)\n")

print_all_fields(keyexchange_pb2)

exit()


if __name__ == "__main__":
    asyncio.run(listen_to_spotify())