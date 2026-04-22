"use client";

import { GoogleOAuthProvider } from "@react-oauth/google";
import { Toaster } from "sonner";

type ProvidersProps = {
    children: React.ReactNode;
};

export default function Providers({ children }: Readonly<ProvidersProps>) {
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "__MISSING_GOOGLE_CLIENT_ID__";
    return (
        <GoogleOAuthProvider clientId={clientId}>
            {children}
            <Toaster richColors position="top-center" />
        </GoogleOAuthProvider>
    );
}
