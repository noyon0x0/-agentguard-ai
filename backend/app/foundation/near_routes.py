"""Read-only NEAR Testnet query endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from .near_client import (
    NearAccountNotFound,
    NearIntegrationError,
    NearInvalidInput,
    NearRpcUnavailable,
    NearTestnetClient,
    NearTransactionNotFound,
    NearWrongNetwork,
)
from .schemas import (
    NearAccountResponse,
    NearContractResponse,
    NearHealthResponse,
    NearTransactionResponse,
)


def create_near_router(client: NearTestnetClient) -> APIRouter:
    router = APIRouter(prefix="/api/v1/near", tags=["NEAR Testnet (read-only)"])

    def get_client() -> NearTestnetClient:
        return client

    @router.get("/health", response_model=NearHealthResponse)
    def rpc_health(near: NearTestnetClient = Depends(get_client)) -> dict:
        try:
            return near.verify_network()
        except NearWrongNetwork as exc:
            raise HTTPException(status_code=503, detail={"code": "NEAR_WRONG_NETWORK"}) from exc
        except NearIntegrationError as exc:
            raise HTTPException(status_code=503, detail={"code": "NEAR_RPC_UNAVAILABLE"}) from exc

    @router.get("/accounts/{account_id}", response_model=NearAccountResponse)
    def account_balance(account_id: str, near: NearTestnetClient = Depends(get_client)) -> dict:
        try:
            return near.get_account(account_id)
        except NearInvalidInput as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_NEAR_ACCOUNT_ID"}) from exc
        except NearAccountNotFound as exc:
            raise HTTPException(status_code=404, detail={"code": "NEAR_ACCOUNT_NOT_FOUND"}) from exc
        except NearWrongNetwork as exc:
            raise HTTPException(status_code=503, detail={"code": "NEAR_WRONG_NETWORK"}) from exc
        except NearRpcUnavailable as exc:
            raise HTTPException(status_code=503, detail={"code": "NEAR_RPC_UNAVAILABLE"}) from exc

    @router.get("/contracts/{account_id}", response_model=NearContractResponse)
    def validate_contract(account_id: str, near: NearTestnetClient = Depends(get_client)) -> dict:
        try:
            account = near.get_account(account_id)
        except NearInvalidInput as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_NEAR_ACCOUNT_ID"}) from exc
        except NearAccountNotFound as exc:
            raise HTTPException(status_code=404, detail={"code": "NEAR_ACCOUNT_NOT_FOUND"}) from exc
        except NearWrongNetwork as exc:
            raise HTTPException(status_code=503, detail={"code": "NEAR_WRONG_NETWORK"}) from exc
        except NearRpcUnavailable as exc:
            raise HTTPException(status_code=503, detail={"code": "NEAR_RPC_UNAVAILABLE"}) from exc
        return {
            "account_id": account["account_id"],
            "network": account["network"],
            "is_contract": account["is_contract"],
            "code_hash": account["code_hash"],
        }

    @router.get("/transactions/{tx_hash}", response_model=NearTransactionResponse)
    def verify_transaction(
        tx_hash: str,
        sender_account_id: str = Query(min_length=2, max_length=64),
        near: NearTestnetClient = Depends(get_client),
    ) -> dict:
        try:
            return near.get_transaction(tx_hash, sender_account_id)
        except NearInvalidInput as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_NEAR_TRANSACTION_REFERENCE"}) from exc
        except NearTransactionNotFound as exc:
            raise HTTPException(status_code=404, detail={"code": "NEAR_TRANSACTION_NOT_FOUND"}) from exc
        except NearWrongNetwork as exc:
            raise HTTPException(status_code=503, detail={"code": "NEAR_WRONG_NETWORK"}) from exc
        except NearRpcUnavailable as exc:
            raise HTTPException(status_code=503, detail={"code": "NEAR_RPC_UNAVAILABLE"}) from exc

    return router
