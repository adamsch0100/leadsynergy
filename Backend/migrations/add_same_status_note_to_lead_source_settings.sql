-- Add same_status_note column to lead_source_settings table
-- This column stores the default note text to use when the lead status hasn't changed

ALTER TABLE lead_source_settings 
ADD COLUMN IF NOT EXISTS same_status_note TEXT DEFAULT 'Same as previous update. Continuing to communicate and assist the referral as best as possible.';

-- Update existing rows to have the default value
UPDATE lead_source_settings 
SET same_status_note = 'Same as previous update. Continuing to communicate and assist the referral as best as possible.'
WHERE same_status_note IS NULL;






