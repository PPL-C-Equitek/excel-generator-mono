DEFAULT_OUTPUT_TABLE_NAME = "result"
MAX_CUSTOM_SCHEMAS_PER_USER = 5
ACTIVE_TRUE_VALUES = frozenset({"true", "1", "yes"})
ACTIVE_FALSE_VALUES = frozenset({"false", "0", "no"})
CUSTOM_SCHEMA_DUPLICATE_NAME_ERROR_MESSAGE = (
    "You already have a custom schema with this name."
)
CUSTOM_SCHEMA_LIMIT_EXCEEDED_ERROR_TEMPLATE = (
    "A user can only have up to {max_count} custom schemas."
)
