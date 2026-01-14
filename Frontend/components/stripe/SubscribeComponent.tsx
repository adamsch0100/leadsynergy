"use client";
import { loadStripe } from "@stripe/stripe-js";
import axios from "axios";
import { useState } from "react";

type props = {
  priceId: string;
  price: string;
  description: string;
  organizationId: string;
};

const SubscribeComponent = ({ priceId, price, description, organizationId }: props) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const handleSubmit = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const stripe = await loadStripe(
        process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY as string
      );

      if (!stripe) {
        setError("Stripe failed to initialize")
        return;
      }

      // Prepare the payload with organizationId if available
      const payload: any = {priceId};
      if (organizationId) {
        payload.organizationId = organizationId;
      }

      // Use the backend URL from environment variable
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001";
      const response = await axios.post(
        `${backendUrl}/api/checkout`,
        payload
      );

      const data = response.data;
      if (!data.ok) throw new Error("Invalid response from server");
      await stripe.redirectToCheckout({
        sessionId: data.session_id,
      });
    } catch (err: any) {
      console.log(err);
      setError(err.message || "Payment initialization failed. Please try again");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      Click Below button to get {description}
      <button
        onClick={handleSubmit}
        className="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded w-full"
        disabled={isLoading}
      >
        {isLoading ? "Processing..." : `Upgrade to ${price}`}
      </button>
    </div>
  );
};

export default SubscribeComponent;
