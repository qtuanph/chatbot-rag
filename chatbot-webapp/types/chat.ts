import { z } from "zod/v4";

import { ChatUIMessageSchema } from "@/lib/schemas";

export type ChatMessage = z.infer<typeof ChatUIMessageSchema>;
