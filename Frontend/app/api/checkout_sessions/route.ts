import { NextResponse } from "next/server";
import { Stripe } from "stripe";

export async function POST(req: Request) {
  try {
    const { priceId } = await req.json();

    const stripe = new Stripe(process.env.STRIPE_SECRET_KEY as string, {
      apiVersion: "2025-04-30.basil",
    });

    const session = await stripe.checkout.sessions.create({
      payment_method_types: ["card"],
      line_items: [
        {
          price: priceId,
          quantity: 1,
        },
      ],
      mode: "subscription",
      success_url: `${process.env.NEXT_PUBLIC_BASE_URL}/signup/billing/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${process.env.NEXT_PUBLIC_BASE_URL}/signup`,
    });

    return NextResponse.json({
      ok: true,
      result: session,
    });
  } catch (err) {
    console.error(err);
    return NextResponse.json(
      { ok: false, err: "Failed to create checkout session" },
      { status: 500 }
    );
  }
}
