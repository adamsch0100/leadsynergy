"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";
import { cookies } from "next/headers";

export async function login(formData: FormData) {
  const supabase = await createClient();

  const data = {
    email: formData.get("email") as string,
    password: formData.get("password") as string,
  };

  const { data: authData, error } = await supabase.auth.signInWithPassword(
    data
  );

  if (error) {
    console.error("[LOGIN] Auth error:", error.message);
    redirect("/error");
  }

  const userId = authData.user?.id;

  const { data: userData, error: userError } = await supabase
    .from("users")
    .select("role")
    .eq("id", userId)
    .single();

  if (userError) {
    console.error("[LOGIN] User role fetch error:", userError.message);
    redirect("/error");
  }

  revalidatePath("/", "layout");

  if (userData?.role === "admin") {
    redirect("/admin/dashboard");
  } else {
    redirect("/agent/dashboard");
  }
}

export async function initiateSignup(formData: FormData) {
  const supabase = await createClient();

  const fullName = formData.get("fullName") as string;
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;
  const organizationName = formData.get("organizationName") as string;
  const fubApiKey = formData.get("fubApiKey") as string;
  const plan = (formData.get("plan") as string) || "free";

  if (!fullName || !email || !password || !organizationName) {
    return { success: false, error: "All fields are required" };
  }

  try {
    // 1. Create the auth user FIRST (before Stripe checkout)
    //    This means we never need to store the password.
    const { data: authData, error: authError } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { full_name: fullName },
      },
    });

    if (authError) {
      return { success: false, error: `Failed to create account: ${authError.message}` };
    }

    if (!authData.user?.id) {
      return { success: false, error: "Failed to create user account" };
    }

    const userId = authData.user.id;

    // 2. Sign in immediately to establish a session
    await supabase.auth.signInWithPassword({ email, password });

    // 3. Create the organization
    const { data: orgData, error: orgError } = await supabase
      .from("organizations")
      .insert({
        name: organizationName,
        slug: organizationName.toLowerCase().replace(/\s+/g, "-"),
        subscription_plan: plan,
        subscription_status: "pending_payment",
        billing_email: email,
      })
      .select()
      .single();

    if (orgError) {
      return {
        success: false,
        error: `Failed to create organization: ${orgError.message}`,
      };
    }

    // 4. Store non-sensitive signup data in cookie for completeSignup
    //    NO password stored — the auth user already exists.
    const signupData = {
      userId,
      fullName,
      email,
      organizationName,
      fubApiKey,
      plan,
      timeStamp: Date.now(),
      organizationId: orgData.id,
    };

    (await cookies()).set({
      name: "signup_data",
      value: JSON.stringify(signupData),
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      maxAge: 60 * 60,
      path: "/",
    });

    return { success: true, organizationId: orgData.id };
  } catch (error: any) {
    console.error("Error initiating signup:", error.message);
    return { success: false, error: "An unexpected error occurred" };
  }
}

export async function completeSignup() {
  const supabase = await createClient();

  // Get signup data from cookie
  const signupDataCookie = (await cookies()).get("signup_data");
  if (!signupDataCookie) {
    return { success: false, error: "Signup session expired" };
  }

  const signupData = JSON.parse(signupDataCookie.value);
  const { userId, organizationId, fullName, email, fubApiKey } = signupData;

  if (!userId) {
    return { success: false, error: "Invalid signup session — missing user ID" };
  }

  // Split full name
  const nameParts = fullName.split(" ");
  const firstName = nameParts[0] || "";
  const lastName = nameParts.slice(1).join(" ") || "";

  // Create user record (auth user already exists from initiateSignup)
  const { error: userError } = await supabase.from("users").insert({
    id: userId,
    email,
    first_name: firstName,
    last_name: lastName,
    full_name: fullName,
    role: "admin",
  });

  if (userError) return { success: false, error: userError.message };

  // Update organization status from pending to active
  const { error: orgUpdateError } = await supabase
    .from("organizations")
    .update({ subscription_status: "active" })
    .eq("id", organizationId);

  if (orgUpdateError) return { success: false, error: orgUpdateError.message };

  // Create organization_users link
  const { error: linkError } = await supabase
    .from("organization_users")
    .insert({
      organization_id: organizationId,
      user_id: userId,
      role: "admin",
    });

  if (linkError) return { success: false, error: linkError.message };

  // Set up FUB API key if provided during signup
  if (fubApiKey && fubApiKey.trim()) {
    try {
      const API_BASE_URL =
        process.env.NEXT_PUBLIC_BACKEND_URL ||
        process.env.NEXT_PUBLIC_API_URL ||
        "http://localhost:8000";

      await fetch(`${API_BASE_URL}/api/setup/fub-api-key`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          api_key: fubApiKey.trim(),
        }),
      });
    } catch (fubError) {
      console.error("Error during FUB setup (non-blocking):", fubError);
    }
  }

  // Clear the signup cookie
  (await cookies()).delete("signup_data");

  return { success: true };
}

export async function signOut() {
  const supabase = await createClient();

  const { error } = await supabase.auth.signOut();

  if (error) {
    console.error("Error signing out:", error.message);
  }

  revalidatePath("/", "layout");
  redirect("/login");
}
