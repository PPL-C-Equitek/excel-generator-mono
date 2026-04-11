export interface CustomSchemaColumnDefinition {
    name: string;
    description: string;
}

export interface CustomSchemaDefinition {
    columns: CustomSchemaColumnDefinition[];
}

export interface CustomSchemaRecord {
    id: string;
    owner_id: string;
    name: string;
    description: string;
    is_active: boolean;
    definition: CustomSchemaDefinition;
    prompt_fragment: string;
    created_at: string;
    updated_at: string;
}

export interface CreateCustomSchemaInput {
    name: string;
    description: string;
    is_active: boolean;
    definition: CustomSchemaDefinition;
}

export interface ICustomSchemaService {
    list: (accessToken: string) => Promise<CustomSchemaRecord[]>;
    create: (
        input: CreateCustomSchemaInput,
        accessToken: string
    ) => Promise<CustomSchemaRecord>;
    update: (
        schemaId: string,
        input: CreateCustomSchemaInput,
        accessToken: string
    ) => Promise<CustomSchemaRecord>;
    remove: (schemaId: string, accessToken: string) => Promise<void>;
}
