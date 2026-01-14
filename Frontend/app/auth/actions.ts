"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";
import { cookies } from "next/headers";

export async function login(formData: FormData) {
  console.log("[LOGIN] Supabase URL:", process.env.NEXT_PUBLIC_SUPABASE_URL);

  const supabase = await createClient();

  // type-casting here for convenience
  // in practice, we should validate the inputs
  const data = {
    email: formData.get("email") as string,
    password: formData.get("password") as string,
  };

  console.log("[LOGIN] Attempting login for:", data.email);
  console.log("[LOGIN] Password received:", data.password ? `${data.password.length} chars, starts with: ${data.password[0]}` : "EMPTY");
  console.log("[LOGIN] FormData keys:", Array.from(formData.keys()));
  console.log("[LOGIN] All FormData entries:");
  formData.forEach((value, key) => {
    console.log(`  ${key}: ${typeof value === 'string' ? value.substring(0, 3) + '...' : value}`);
  });

  const { data: authData, error } = await supabase.auth.signInWithPassword(
    data
  );

  if (error) {
    console.error("[LOGIN] Auth error:", error.message, error);
    redirect("/error");
  }

  console.log("[LOGIN] Auth successful, user ID:", authData.user?.id);

  // Check the table 'users' for the role and then redirect accordingly
  const userId = authData.user?.id;

  // Query the users table to get the role
  const { data: userData, error: userError } = await supabase
    .from("users")
    .select("role")
    .eq("id", userId)
    .single();

  if (userError) {
    console.error("[LOGIN] User role fetch error:", userError.message, userError);
    redirect("/error");
  }

  console.log("[LOGIN] User role:", userData?.role);

  revalidatePath("/", "layout");

  // Redirect based on role
  if (userData?.role === "admin") {
    redirect("/admin/dashboard");
  } else {
    redirect("/agent/dashboard");
  }
}

export async function initiateSignup(formData: FormData) {
  const supabase = await createClient();
  // Extract form data
  const fullName = formData.get("fullName") as string;
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;
  const organizationName = formData.get("organizationName") as string;
  const fubApiKey = formData.get("fubApiKey") as string;
  const plan = (formData.get("plan") as string) || "free";

  // Basic validation
  if (!fullName || !email || !password || !organizationName) {
    return { success: false, error: "All fields are required" };
  }

  try {
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
    // Store signup data in a secure HTTP-only cookie
    // This temporarily holds the data without creating permanent records
    const signupData = {
      fullName,
      email,
      password,
      organizationName,
      fubApiKey,
      plan,
      timeStamp: Date.now(),
      organizationId: orgData.id,
    };

    // Set cookie with signup data that expires in 1 hour
    (await cookies()).set({
      name: "signup_data",
      value: JSON.stringify(signupData),
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      maxAge: 60 * 60,
      path: "/",
    });

    console.log("Setting cookie with data:", signupData);
    return { success: true, organizationId: orgData.id };
  } catch (error: any) {
    console.error("Error initiating signup:", error.message);
    return { success: false, error: "An unexpected occurred" };
  }
}

// Deprecated
// export async function completeSignup() {
//   const supabase = await createClient();

//   console.log("Starting completeSignup function");

//   try {
//     // Retrieve signup data from cookie
//     const signupDataCookie = (await cookies()).get("signup_data");
//     console.log("Cookie exists:", !!signupDataCookie);

//     if (!signupDataCookie) {
//       console.error("Signup data cookie not found");
//       return { success: false, error: "Signup session expired or not found" };
//     }

//     try {
//       const signupData = JSON.parse(signupDataCookie.value);
//       console.log("Parsed signup data:", {
//         email: signupData.email,
//         fullName: signupData.fullName,
//         organizationName: signupData.organizationName,
//         plan: signupData.plan,
//         // Don't log the password
//       });

//       // Check if session is too old
//       const now = Date.now();
//       if (now - signupData.timeStamp > 3600000) {
//         (await cookies()).delete("signup_data");
//         console.error("Signup session expired (timestamp check)");
//         return { success: false, error: "Signup session expired" };
//       }

//       // Extract data
//       const { fullName, email, password, organizationName, plan } = signupData;

//       // Split full name
//       const nameParts = fullName.split(" ");
//       const firstName = nameParts[0] || "";
//       const lastName = nameParts.slice(1).join(" ") || "";

//       console.log("Creating Supabase auth user");
//       // Create user in Supabase Auth
//       const { data: authData, error: authError } = await supabase.auth.signUp({
//         email,
//         password,
//       });

//       if (authError) {
//         console.error("Auth signup error:", authError.message);
//         return { success: false, error: `Auth error: ${authError.message}` };
//       }

//       if (!authData?.user?.id) {
//         console.error("Auth data is missing user ID");
//         return { success: false, error: "Failed to create auth user account" };
//       }

//       console.log("Auth user created successfully with ID:", authData.user.id);

//       // First create organization
//       console.log("Creating organization record");
//       const { data: orgData, error: orgError } = await supabase
//         .from("organizations")
//         .insert({
//           name: organizationName,
//           slug: organizationName.toLowerCase().replace(/\s+/g, "-"),
//           subscription_plan: plan,
//           subscription_status: "trial",
//           billing_email: email,
//         })
//         .select()
//         .single();

//       if (orgError) {
//         console.error("Error creating organization:", orgError);
//         return {
//           success: false,
//           error: `Failed to create organization: ${orgError.message}`,
//         };
//       }

//       console.log("Organization created successfully with ID:", orgData.id);

//       // Create user with admin role
//       console.log("Creating user record");
//       const { error: userError } = await supabase.from("users").insert({
//         id: authData.user.id,
//         email,
//         first_name: firstName,
//         last_name: lastName,
//         full_name: fullName,
//         role: "admin",
//       });

//       if (userError) {
//         console.error("Error creating user record:", userError);
//         return {
//           success: false,
//           error: `Failed to create user record: ${userError.message}`,
//         };
//       }

//       console.log("User record created successfully");

//       try {
//         // Create organization_users link
//         console.log("Creating organization_users link");
//         const { error: orgUserError } = await supabase
//           .from("organization_users")
//           .insert({
//             organization_id: orgData.id,
//             user_id: authData.user.id,
//             role: "admin",
//           });

//         if (orgUserError) {
//           console.error("Error creating organization user link:", orgUserError);
//           return {
//             success: false,
//             error: `Failed to link user to organization: ${orgUserError.message}`,
//           };
//         }

//         console.log("Organization user link created successfully");
//       } catch (linkError) {
//         console.error(
//           "Exception during organization link creation:",
//           linkError
//         );
//         return {
//           success: false,
//           error: "Exception during organization link creation",
//         };
//       }

//       // Clear the signup cookie
//       console.log("Clearing signup cookie");
//       (await cookies()).delete("signup_data");

//       // Sign in the user
//       console.log("Signing in the user");
//       await supabase.auth.signInWithPassword({
//         email,
//         password,
//       });

//       console.log("Account setup completed successfully");
//       revalidatePath("/", "layout");
//       return { success: true };
//     } catch (parseError) {
//       console.error("Error parsing cookie data:", parseError);
//       return { success: false, error: "Invalid signup data" };
//     }
//   } catch (error: any) {
//     console.error("Complete signup top-level error:", error);
//     return {
//       success: false,
//       error: error.message || "An unexpected error occurred",
//     };
//   }
// }

export async function completeSignup() {
  const supabase = await createClient();

  // Get signup data from cookie
  const signupDataCookie = (await cookies()).get("signup_data");
  if (!signupDataCookie) {
    return { success: false, error: "Signup session expired" };
  }

  const signupData = JSON.parse(signupDataCookie.value);
  const { organizationId, fullName, email, password, fubApiKey } = signupData;

  // Create auth user
  const { data: authData, error: authError } = await supabase.auth.signUp({
    email,
    password,
  });

  if (authError) return { success: false, error: authError.message };

  // Split full name
  const nameParts = fullName.split(" ");
  const firstName = nameParts[0] || "";
  const lastName = nameParts.slice(1).join(" ") || "";

  // Create user record
  const { error: userError } = await supabase.from("users").insert({
    id: authData.user?.id,
    email: email,
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
      user_id: authData.user?.id,
      role: "admin",
    });

  if (linkError) return { success: false, error: linkError.message };

  // Set up FUB API key and trigger initial import if provided
  if (fubApiKey && fubApiKey.trim()) {
    try {
      console.log("Setting up FUB API key for new user");

      // Call the backend API to setup FUB API key
      const fubResponse = await fetch("/api/setup/fub-api-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: authData.user?.id,
          api_key: fubApiKey.trim()
        })
      });

      if (!fubResponse.ok) {
        console.error("Failed to setup FUB API key, but continuing with signup");
      } else {
        console.log("FUB API key setup successfully, triggering initial import");

        // Trigger initial FUB import (this will run in background)
        const importResponse = await fetch("/api/supabase/import-fub-leads", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-User-ID": authData.user?.id || ""
          }
        });

        if (!importResponse.ok) {
          console.error("Failed to trigger initial FUB import, but continuing with signup");
        } else {
          console.log("Initial FUB import triggered successfully");
        }
      }
    } catch (fubError) {
      console.error("Error during FUB setup, but continuing with signup:", fubError);
    }
  }

  // Clear cookie and sign in user
  (await cookies()).delete("signup_data");
  await supabase.auth.signInWithPassword({ email, password });

  return { success: true };
}
export async function signOut() {
  const supabase = await createClient();

  // Sign out the user from Supabase auth
  const { error } = await supabase.auth.signOut();

  if (error) {
    console.error("Error signing out:", error.message);
  }

  // Force revalidation of the layout to update auth state across the app
  revalidatePath("/", "layout");

  // Redirect to the login page
  redirect("/login");
}
