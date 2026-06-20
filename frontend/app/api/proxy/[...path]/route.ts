import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000/api/v1";
const BACKEND_API_KEY = process.env.BACKEND_API_KEY ?? "";
const PLACEHOLDER_KEY = "change-me-to-a-long-random-string";

async function handler(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  if (!BACKEND_API_KEY || BACKEND_API_KEY === PLACEHOLDER_KEY) {
    return NextResponse.json(
      {
        detail:
          "BACKEND_API_KEY is missing or still the placeholder. Set it in frontend/.env.local to match API_KEY in the backend .env, then restart `npm run dev`.",
      },
      { status: 500 }
    );
  }

  const { path } = await params;
  const pathname = path.join("/");
  const search = req.nextUrl.search;
  const url = `${BACKEND_URL}/${pathname}${search}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-API-Key": BACKEND_API_KEY,
  };

  const body =
    req.method !== "GET" && req.method !== "HEAD"
      ? await req.text()
      : undefined;

  const upstream = await fetch(url, {
    method: req.method,
    headers,
    body,
  });

  const data = await upstream.text();
  return new NextResponse(data, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
