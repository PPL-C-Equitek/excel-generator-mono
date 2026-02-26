import { fetchAPI } from "@/lib/api";

export async function generateJson(inputJson: any): Promise<any> {
    if (Object.keys(inputJson).length === 0) {
        throw new Error("Input tidak boleh kosong");
    }

    try {
        const data = await fetchAPI("llm/generate/", {
            method: "POST",
            body: JSON.stringify({ input_json: inputJson }),
        });

        if (!data || !data.output_json) {
            throw new Error("Respons tidak sesuai skema");
        }
        return data;
    } catch (err: any) {
        if (err.message.includes("401")) throw new Error("API Key tidak valid");
        if (err.message.includes("429")) throw new Error("Quota LLM habis, coba lagi nanti");
        if (err.message.includes("504")) throw new Error("Request timeout, coba lagi");
        throw err;
    }
}