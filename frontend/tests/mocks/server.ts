import { setupServer } from "msw/node";
import { handlers } from "./handlers";

// MSW server untuk Node/Vitest environment
export const server = setupServer(...handlers);
