import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
    fetchAPI,
    login,
    uploadFile,
    loginWithGoogle,
    logout,
    changePassword,
    requestPasswordReset,
    resendPasswordReset,
} from "@/lib/api";

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

describe("fetchAPI", () => {
    afterEach(() => {
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
        vi.unstubAllEnvs();
    });

    it("calls API endpoint and returns parsed JSON", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ status: "ok" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const result = await fetchAPI("health/");

        expect(mockedFetch).toHaveBeenCalledWith("http://localhost:8000/health/", {
            headers: {
                "Content-Type": "application/json",
            },
        });
        expect(result).toEqual({ status: "ok" });
    });

    it("throws error when response is not OK", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
            json: async () => ({}),
        });
        vi.stubGlobal("fetch", mockedFetch);

        await expect(fetchAPI("health/")).rejects.toThrow("Request failed. Please try again.");
    });

    it("strips trailing slash from NEXT_PUBLIC_API_URL before building request URL", async () => {
        vi.resetModules();
        vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:9999/");

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ status: "trimmed" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const { fetchAPI: freshFetchAPI } = await import("@/lib/api");
        const result = await freshFetchAPI("health/");

        const calledUrl = mockedFetch.mock.calls[0][0] as string;
        expect(calledUrl).toBe("http://localhost:9999/health/");
        expect(result).toEqual({ status: "trimmed" });
    });

    it("clears auth tokens and redirects to /login when a protected request returns 401", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 401,
            json: async () => ({ message: "Unauthorized" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        window.localStorage.setItem("access_token", "access-token");
        window.localStorage.setItem("refresh_token", "refresh-token");

        const removeItemSpy = vi.spyOn(Storage.prototype, "removeItem");
        const assignSpy = vi.fn();
        Object.defineProperty(window, "location", {
            configurable: true,
            value: {
                ...window.location,
                assign: assignSpy,
            },
        });

        await expect(
            fetchAPI("history/", {
                headers: {
                    Authorization: "Bearer access-token",
                },
            })
        ).rejects.toMatchObject({
            status: 401,
        });

        expect(removeItemSpy).toHaveBeenCalledWith("access_token");
        expect(removeItemSpy).toHaveBeenCalledWith("refresh_token");
        expect(assignSpy).toHaveBeenCalledWith("/login");
    });

    it("still throws the 401 error gracefully when window is unavailable", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 401,
            json: async () => ({ message: "Unauthorized" }),
        });
        vi.stubGlobal("fetch", mockedFetch);
        vi.stubGlobal("window", undefined);

        await expect(fetchAPI("history/")).rejects.toMatchObject({
            status: 401,
            message: "Unauthorized",
        });
    });

    it("clears auth tokens without redirecting again when already on /login", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 401,
            json: async () => ({ message: "Unauthorized" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        window.localStorage.setItem("access_token", "access-token");
        window.localStorage.setItem("refresh_token", "refresh-token");

        const removeItemSpy = vi.spyOn(Storage.prototype, "removeItem");
        const assignSpy = vi.fn();
        Object.defineProperty(window, "location", {
            configurable: true,
            value: {
                ...window.location,
                pathname: "/login",
                assign: assignSpy,
            },
        });

        await expect(fetchAPI("history/")).rejects.toMatchObject({
            status: 401,
        });

        expect(removeItemSpy).toHaveBeenCalledWith("access_token");
        expect(removeItemSpy).toHaveBeenCalledWith("refresh_token");
        expect(assignSpy).not.toHaveBeenCalled();
    });
});

describe("uploadFile", () => {
    beforeEach(() => {
        delete process.env.NEXT_PUBLIC_API_URL;
    });

    afterEach(() => {
        process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
        vi.unstubAllEnvs();
    });

    it("uploads file as FormData and returns parsed response", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 201,
            json: async () => ({ message: "uploaded" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "report.xlsx", {
            type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        });

        const result = await uploadFile(file);

        expect(mockedFetch).toHaveBeenCalledWith(
            "http://localhost:8000/upload/",
            expect.objectContaining({
                method: "POST",
                body: expect.any(FormData),
            })
        );
        expect(result).toEqual({ message: "uploaded" });
    });

    it("throws API error message when upload fails with message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "Invalid file" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "bad.txt", { type: "text/plain" });

        await expect(uploadFile(file)).rejects.toThrow("Invalid file");
    });

    it("maps max file size upload error to user-friendly FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "File too large. Maximum allowed size is 10MB." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "big.pdf", { type: "application/pdf" });

        await expect(uploadFile(file)).rejects.toThrow("File size too big.");
    });

    it("maps max PDF page count error to user-friendly FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({
                message: "PDF exceeds the maximum allowed page count of 100.",
            }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "long.pdf", { type: "application/pdf" });

        await expect(uploadFile(file)).rejects.toThrow("PDF has too many pages (maximum 100).");
    });

    it("maps max Excel sheet count error to user-friendly FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({
                message: "Excel has too many sheets (maximum 100).",
            }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "many.xlsx", {
            type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        });

        await expect(uploadFile(file)).rejects.toThrow("Excel has too many sheets (maximum 100).");
    });

    it("maps password-protected PDF error to dedicated FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "PDF file is password-protected." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "protected.pdf", { type: "application/pdf" });

        await expect(uploadFile(file)).rejects.toThrow(
            "PDF is password-protected. Please remove the password and try again."
        );
    });

    it("maps password-protected Excel error to dedicated FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({
                message:
                    "Excel file is password-protected. Please remove the password and try again.",
            }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "protected.xlsx", {
            type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        });

        await expect(uploadFile(file)).rejects.toThrow(
            "Excel is password-protected. Please remove the password and try again."
        );
    });

    it("maps password-protected Word error to dedicated FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "Word file is password-protected." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "protected.docx", {
            type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        });

        await expect(uploadFile(file)).rejects.toThrow(
            "Word file is password-protected. Please remove the password and try again."
        );
    });

    it("maps corrupted PDF error to dedicated FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "PDF file is corrupt or has an invalid structure." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "corrupt.pdf", { type: "application/pdf" });

        await expect(uploadFile(file)).rejects.toThrow("PDF file is corrupted or invalid.");
    });

    it("maps PDF invalid structure error when message does not include exact corrupt phrase", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "PDF parser encountered invalid structure in cross-reference table." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "invalid.pdf", { type: "application/pdf" });

        await expect(uploadFile(file)).rejects.toThrow("PDF file is corrupted or invalid.");
    });

    it("maps corrupted Word error to dedicated FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "Word file is corrupt or has an invalid structure." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "corrupt.docx", {
            type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        });

        await expect(uploadFile(file)).rejects.toThrow("Word file is corrupt or has an invalid structure.");
    });

    it("maps Word invalid structure error when message does not include corrupt keyword", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "Word parser error: invalid structure detected." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "invalid.docx", {
            type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        });

        await expect(uploadFile(file)).rejects.toThrow("Word file is corrupt or has an invalid structure.");
    });

    it("maps max Word page count error to user-friendly FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({
                message: "Word exceeds the maximum allowed page count of 100.",
            }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "long.docx", {
            type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        });

        await expect(uploadFile(file)).rejects.toThrow("Word has too many pages (maximum 100).");
    });

    it("maps generic corrupted Excel error to dedicated FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "Invalid or corrupted Excel file." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "corrupt.xlsx", {
            type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        });

        await expect(uploadFile(file)).rejects.toThrow("Excel file is corrupt or has an invalid structure.");
    });

    it("maps parser-level corrupted Excel error to dedicated FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "File Excel corrupted atau cannot read: broken stream" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "corrupt.xls", {
            type: "application/vnd.ms-excel",
        });

        await expect(uploadFile(file)).rejects.toThrow("Excel file is corrupt or has an invalid structure.");
    });

    it("maps strictly 'cannot read' Excel error to dedicated FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "Excel error: cannot read format" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "cannot_read.xls", {
            type: "application/vnd.ms-excel",
        });

        await expect(uploadFile(file)).rejects.toThrow("Excel file is corrupt or has an invalid structure.");
    });

    it("maps rate-limit upload error from message field", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 429,
            json: async () => ({ message: "Rate limit exceeded. Try again later." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "report.pdf", { type: "application/pdf" });

        await expect(uploadFile(file)).rejects.toThrow(
            "Rate limit exceeded. Please try again later."
        );
    });

    it("maps rate-limit upload error from detail field", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 429,
            json: async () => ({ detail: "Too many uploads." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "report.pdf", { type: "application/pdf" });

        await expect(uploadFile(file)).rejects.toThrow(
            "Rate limit exceeded. Please try again later."
        );
    });

    it("maps generic password-protected error when file type is unspecified", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "This file is password-protected." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "archive.bin", {
            type: "application/octet-stream",
        });

        await expect(uploadFile(file)).rejects.toThrow(
            "File is password-protected. Please remove the password and try again."
        );
    });

    it("throws default error when upload fails without message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
            json: async () => ({}),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "bad.txt", { type: "text/plain" });

        await expect(uploadFile(file)).rejects.toThrow("Upload failed");
    });

    it("preserves the configured API path when uploading files", async () => {
        vi.resetModules();
        vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:9999/api/v1/");

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ message: "ok" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const { uploadFile: freshUploadFile } = await import("@/lib/api");
        const file = new File(["content"], "test.pdf", { type: "application/pdf" });
        await freshUploadFile(file);

        const calledUrl = mockedFetch.mock.calls[0][0] as string;
        expect(calledUrl).toBe("http://localhost:9999/api/v1/upload/");
    });
});

// Login Tests

const mockFetch = vi.spyOn(global, 'fetch')
vi.stubGlobal('fetch', mockFetch)

function mockResponse(body: unknown, status = 200) {
    return {
        ok: status >= 200 && status < 300,
        status,
        json: vi.fn().mockResolvedValue(body),
    } as unknown as Response
}

describe('login', () => {
    beforeEach(() => {
        mockFetch.mockClear()
    })

    describe('positive', () => {
        it('calls fetch with correct URL and method', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ access_token: 'abc', refresh_token: 'xyz' }))

            await login('user1@gmail.com', 'user1123')

            expect(mockFetch).toHaveBeenCalledWith(
                expect.stringContaining('auth/login/'),
                expect.objectContaining({
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                })
            )
        })

        it('calls fetch with email and password in request body', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ access_token: 'abc', refresh_token: 'xyz' }))

            await login('user1@gmail.com', 'user1123')

            const body = JSON.parse(mockFetch.mock.calls[0][1].body)
            expect(body).toEqual({ email: 'user1@gmail.com', password: 'user1123' })
        })

        it('returns parsed JSON on success', async () => {
            const payload = { access_token: 'abc', refresh_token: 'xyz' }
            mockFetch.mockResolvedValueOnce(mockResponse(payload))

            const result = await login('user1@gmail.com', 'user1123')

            expect(result).toEqual(payload)
        })
    })

    describe('negative', () => {
        it('throws error with message from response body (message field)', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ message: 'Invalid credentials' }, 401))

            await expect(login('user1@gmail.com', 'wrongpassword')).rejects.toThrow('Invalid credentials')
        })

        it('throws error with message from response body (detail field)', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ detail: 'Email not verified' }, 401))

            await expect(login('user1@gmail.com', 'user1123')).rejects.toThrow('Email not verified')
        })

        it('throws error with fallback message when response body has no message or detail', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({}, 500))

            await expect(login('user1@gmail.com', 'user1123')).rejects.toThrow('Request failed. Please try again.')
        })

        it('throws error with fallback message when response body is not valid JSON', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                json: vi.fn().mockRejectedValue(new SyntaxError('Invalid JSON')),
            } as unknown as Response)

            await expect(login('user1@gmail.com', 'user1123')).rejects.toThrow('Request failed. Please try again.')
        })

        it('throws HTTPError with correct status code', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ detail: 'Email not verified' }, 401))

            const error = await login('user1@gmail.com', 'user1123').catch(e => e)
            expect(error.status).toBe(401)
        })
    })

    describe('edge case', () => {
        it('sends email as-is without normalization', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ access_token: 'abc', refresh_token: 'xyz' }))

            await login('  USER1@GMAIL.COM  ', 'user1123')

            const body = JSON.parse(mockFetch.mock.calls[0][1].body)
            expect(body.email).toBe('  USER1@GMAIL.COM  ')
        })

        it('constructs URL with correct endpoint path', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ access_token: 'abc', refresh_token: 'xyz' }))

            await login('user1@gmail.com', 'user1123')

            const url = mockFetch.mock.calls[0][0] as string
            expect(url).toMatch(/\/auth\/login\/$/)
        })

        it('uses fallback message when response body message field is not a string', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ message: 123 }, 400))

            await expect(login('user1@gmail.com', 'user1123')).rejects.toThrow('Request failed. Please try again.')
        })

        it('uses fallback message when response body detail field is not a string', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ detail: ['error'] }, 400))

            await expect(login('user1@gmail.com', 'user1123')).rejects.toThrow('Request failed. Please try again.')
        })

        it('throws when fetch rejects due to network error', async () => {
            mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))

            await expect(login('user1@gmail.com', 'user1123')).rejects.toThrow('Failed to fetch')
        })
    })
})

describe('loginWithGoogle', () => {
    beforeEach(() => {
        mockFetch.mockClear()
    })

    describe('positive', () => {
        it('calls fetch with correct URL and method', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({
                access_token: 'abc',
                refresh_token: 'xyz',
                user: { id: 1, email: 'user1@gmail.com', name: 'User 1' },
            }))

            await loginWithGoogle('mock-google-token')

            expect(mockFetch).toHaveBeenCalledWith(
                expect.stringContaining('auth/google-oauth/'),
                expect.objectContaining({
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                })
            )
        })

        it('calls fetch with token in request body', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({
                access_token: 'abc',
                refresh_token: 'xyz',
                user: { id: 1, email: 'user1@gmail.com', name: 'User 1' },
            }))

            await loginWithGoogle('mock-google-token')

            const body = JSON.parse(mockFetch.mock.calls[0][1].body)
            expect(body).toEqual({ token: 'mock-google-token' })
        })

        it('returns parsed AuthResponse on success', async () => {
            const payload = {
                access_token: 'abc',
                refresh_token: 'xyz',
                user: { id: 1, email: 'user1@gmail.com', name: 'User 1' },
            }
            mockFetch.mockResolvedValueOnce(mockResponse(payload))

            const result = await loginWithGoogle('mock-google-token')

            expect(result).toEqual(payload)
        })
    })

    describe('negative', () => {
        it('throws error with message from response body (message field)', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ message: 'Invalid token' }, 401))

            await expect(loginWithGoogle('bad-token')).rejects.toThrow('Invalid token')
        })

        it('throws error with message from response body (detail field)', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ detail: 'Token expired' }, 401))

            await expect(loginWithGoogle('bad-token')).rejects.toThrow('Token expired')
        })

        it('throws error with fallback message when response body has no message or detail', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({}, 500))

            await expect(loginWithGoogle('mock-google-token')).rejects.toThrow('Request failed. Please try again.')
        })

        it('throws error with fallback message when response body is not valid JSON', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                json: vi.fn().mockRejectedValue(new SyntaxError('Invalid JSON')),
            } as unknown as Response)

            await expect(loginWithGoogle('mock-google-token')).rejects.toThrow('Request failed. Please try again.')
        })

        it('throws HTTPError with correct status code', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ message: 'Invalid token' }, 401))

            const error = await loginWithGoogle('bad-token').catch(e => e)
            expect(error.status).toBe(401)
        })
    })

    describe('edge case', () => {
        it('constructs URL with correct endpoint path', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({
                access_token: 'abc',
                refresh_token: 'xyz',
                user: { id: 1, email: 'user1@gmail.com', name: 'User 1' },
            }))

            await loginWithGoogle('mock-google-token')

            const url = mockFetch.mock.calls[0][0] as string
            expect(url).toMatch(/\/auth\/google-oauth\/$/)
        })

        it('throws when fetch rejects due to network error', async () => {
            mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))

            await expect(loginWithGoogle('mock-google-token')).rejects.toThrow('Failed to fetch')
        })

        it('uses fallback message when response body message field is not a string', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ message: 123 }, 400))

            await expect(loginWithGoogle('mock-google-token')).rejects.toThrow('Request failed. Please try again.')
        })

        it('uses fallback message when response body detail field is not a string', async () => {
            mockFetch.mockResolvedValueOnce(mockResponse({ detail: ['error'] }, 400))

            await expect(loginWithGoogle('mock-google-token')).rejects.toThrow('Request failed. Please try again.')
        })
    })
})

describe('logout', () => {
    beforeEach(() => {
        mockFetch.mockClear()
        vi.stubGlobal('fetch', mockFetch)
    })

    it('calls the logout endpoint with bearer access token and refresh token payload', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            status: 200,
            json: vi.fn(),
        } as unknown as Response)

        await logout('access-token', 'refresh-token')

        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/auth/logout/'),
            expect.objectContaining({
                method: 'POST',
                headers: {
                    Authorization: 'Bearer access-token',
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ refresh_token: 'refresh-token' }),
            })
        )
    })

    it('strips trailing slash from NEXT_PUBLIC_API_URL before building logout URL', async () => {
        vi.resetModules()
        vi.stubEnv('NEXT_PUBLIC_API_URL', 'http://localhost:9999/')

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: vi.fn(),
        })
        vi.stubGlobal('fetch', mockedFetch)

        const { logout: freshLogout } = await import('@/lib/api')
        await freshLogout('access-token', 'refresh-token')

        expect(mockedFetch).toHaveBeenCalledWith(
            'http://localhost:9999/auth/logout/',
            expect.objectContaining({ method: 'POST' })
        )
    })

    it('throws message from response body when logout fails', async () => {
        mockFetch.mockResolvedValueOnce(mockResponse({ message: 'Unauthorized' }, 401))

        await expect(logout('access-token', 'refresh-token')).rejects.toThrow('Unauthorized')
    })

    it('throws detail from response body when logout fails', async () => {
        mockFetch.mockResolvedValueOnce(mockResponse({ detail: 'Token invalid' }, 401))

        await expect(logout('access-token', 'refresh-token')).rejects.toThrow('Token invalid')
    })

    it('prefers detail when logout message field is present but not a string', async () => {
        mockFetch.mockResolvedValueOnce(
            mockResponse({ message: ['bad'], detail: 'Token invalid' }, 401)
        )

        await expect(logout('access-token', 'refresh-token')).rejects.toThrow('Token invalid')
    })

    it('falls back to the generic error when logout response JSON has no string message or detail', async () => {
        mockFetch.mockResolvedValueOnce(
            mockResponse({ message: ['bad'], detail: ['still-bad'] }, 401)
        )

        await expect(logout('access-token', 'refresh-token')).rejects.toThrow(
            'Logout gagal. Silakan coba lagi.'
        )
    })

    it('falls back to a generic error when logout response body cannot be parsed', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: false,
            status: 500,
            json: vi.fn().mockRejectedValue(new SyntaxError('Invalid JSON')),
        } as unknown as Response)

        await expect(logout('access-token', 'refresh-token')).rejects.toThrow(
            'Logout gagal. Silakan coba lagi.'
        )
    })
})

describe('changePassword', () => {
    beforeEach(() => {
        mockFetch.mockClear()
        vi.stubGlobal('fetch', mockFetch)
    })

    it('calls the change-password endpoint with bearer token and payload', async () => {
        mockFetch.mockResolvedValueOnce(
            mockResponse({ message: 'Password changed successfully.' })
        )

        await changePassword('access-token', {
            current_password: 'Current#123',
            new_password: 'Updated#123',
            new_password_confirm: 'Updated#123',
            refresh_token: 'refresh-token',
        })

        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/auth/change-password/'),
            expect.objectContaining({
                method: 'POST',
                headers: {
                    Authorization: 'Bearer access-token',
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    current_password: 'Current#123',
                    new_password: 'Updated#123',
                    new_password_confirm: 'Updated#123',
                    refresh_token: 'refresh-token',
                }),
            })
        )
    })

    it('returns parsed JSON on success', async () => {
        mockFetch.mockResolvedValueOnce(
            mockResponse({ message: 'Password changed successfully.' })
        )

        const result = await changePassword('access-token', {
            current_password: '',
            new_password: 'Updated#123',
            new_password_confirm: 'Updated#123',
        })

        expect(result).toEqual({ message: 'Password changed successfully.' })
    })

    it('throws API message on failure', async () => {
        mockFetch.mockResolvedValueOnce(
            mockResponse({ message: 'Current password is incorrect.' }, 400)
        )

        await expect(
            changePassword('access-token', {
                current_password: 'Wrong#123',
                new_password: 'Updated#123',
                new_password_confirm: 'Updated#123',
            })
        ).rejects.toThrow('Current password is incorrect.')
    })

    it('falls back to a generic error when no message is present', async () => {
        mockFetch.mockResolvedValueOnce(mockResponse({}, 500))

        await expect(
            changePassword('access-token', {
                current_password: 'Current#123',
                new_password: 'Updated#123',
                new_password_confirm: 'Updated#123',
            })
        ).rejects.toThrow('Failed to change password.')
    })

    it('uses detail when change-password failure returns no string message', async () => {
        mockFetch.mockResolvedValueOnce(
            mockResponse({ message: ['bad'], detail: 'Token invalid' }, 401)
        )

        await expect(
            changePassword('access-token', {
                current_password: 'Current#123',
                new_password: 'Updated#123',
                new_password_confirm: 'Updated#123',
            })
        ).rejects.toThrow('Token invalid')
    })
})

describe('password reset API helpers', () => {
    beforeEach(() => {
        mockFetch.mockClear()
    })

    it('requestPasswordReset posts the email to the forgot-password endpoint', async () => {
        mockFetch.mockResolvedValueOnce(mockResponse({ message: 'ok' }))

        await requestPasswordReset('user@example.com')

        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/auth/forgot-password/'),
            expect.objectContaining({
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: 'user@example.com' }),
            })
        )
    })

    it('resendPasswordReset posts the email to the resend-password-reset endpoint', async () => {
        mockFetch.mockResolvedValueOnce(mockResponse({ message: 'ok' }))

        await resendPasswordReset('user@example.com')

        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/auth/resend-password-reset/'),
            expect.objectContaining({
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: 'user@example.com' }),
            })
        )
    })
})
