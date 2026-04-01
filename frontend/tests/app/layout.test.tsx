import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import RootLayout from "@/app/layout";

describe("RootLayout", () => {
    it("wraps children and applies html/body structure", () => {
        const html = renderToStaticMarkup(
            <RootLayout>
                <div>Child Content</div>
            </RootLayout>,
        );

        expect(html).toContain("lang=\"en\"");
        expect(html).toContain("Child Content");
        expect(html).toContain("font-geist-sans");
        expect(html).toContain("font-geist-mono");
    });
});