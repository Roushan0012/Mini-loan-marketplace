import { apiClient } from '../../../services/apiClient';
import {
  MockKFSResponse,
  OfferGenerationResponse,
  OfferResponse,
  OfferSelectionResponse,
} from '../types';

export const offerService = {
  /**
   * Generate mock loan offers for eligible lender decisions from the latest completed match run.
   */
  async generateOffers(applicationId: number | string): Promise<OfferGenerationResponse> {
    return apiClient.post<OfferGenerationResponse>(
      `/applications/${applicationId}/offers/generate`
    );
  },

  /**
   * Retrieve all credit offers belonging to the latest completed match run.
   */
  async listOffers(applicationId: number | string): Promise<OfferResponse[]> {
    return apiClient.get<OfferResponse[]>(`/applications/${applicationId}/offers`);
  },

  /**
   * Retrieve Key Facts Statement (KFS) details for a specific loan offer.
   */
  async getMockKFS(
    applicationId: number | string,
    offerId: number | string
  ): Promise<MockKFSResponse> {
    return apiClient.get<MockKFSResponse>(
      `/applications/${applicationId}/offers/${offerId}/kfs`
    );
  },

  /**
   * Select exactly one available loan offer for a matched loan application.
   */
  async selectOffer(
    applicationId: number | string,
    offerId: number | string
  ): Promise<OfferSelectionResponse> {
    return apiClient.post<OfferSelectionResponse>(
      `/applications/${applicationId}/offers/${offerId}/select`
    );
  },
};
