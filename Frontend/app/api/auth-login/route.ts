import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const body = await request.json();
  const { email, password } = body;

  console.log("[TEST-LOGIN] Starting test...");
  console.log("[TEST-LOGIN] URL:", process.env.NEXT_PUBLIC_SUPABASE_URL);
  console.log("[TEST-LOGIN] Key starts:", process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.substring(0, 30));
  console.log("[TEST-LOGIN] Email:", email);
  console.log("[TEST-LOGIN] Password length:", password?.length);

  try {
    const supabase = await createClient();

    console.log("[TEST-LOGIN] Supabase client created, attempting login...");

    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      console.error("[TEST-LOGIN] Auth error:", error);
      return NextResponse.json({
        success: false,
        error: error.message,
        errorCode: error.status,
        fullError: JSON.stringify(error)
      }, { status: 400 });
    }

    console.log("[TEST-LOGIN] Auth success, user:", data.user?.id);

    // Try to fetch role
    const { data: userData, error: userError } = await supabase
      .from("users")
      .select("role")
      .eq("id", data.user?.id)
      .single();

    if (userError) {
      console.error("[TEST-LOGIN] User fetch error:", userError);
      return NextResponse.json({
        success: false,
        error: "User role fetch failed",
        userError: JSON.stringify(userError)
      }, { status: 400 });
    }

    console.log("[TEST-LOGIN] Complete success! Role:", userData?.role);

    return NextResponse.json({
      success: true,
      userId: data.user?.id,
      email: data.user?.email,
      role: userData?.role
    });

  } catch (e: any) {
    console.error("[TEST-LOGIN] Exception:", e);
    return NextResponse.json({
      success: false,
      error: e.message,
      stack: e.stack
    }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({
    message: "Use POST with {email, password}"
  });
}
