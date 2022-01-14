#include <iostream>
#include <memory>
#include <unordered_map>

#include "mlir/Transforms/DialectConversion.h"
#include "mlir/Dialect/Affine/IR/AffineOps.h"
#include "mlir/Dialect/SCF/SCF.h"
#include "mlir/Dialect/Tensor/IR/Tensor.h"

#include "abc/IR/FHE/FHEDialect.h"
#include "abc/Passes/ssa2ssa/Batching.h"

using namespace mlir;

void BatchingPass::getDependentDialects(mlir::DialectRegistry &registry) const {
  registry.insert<fhe::FHEDialect,
                  mlir::AffineDialect,
                  mlir::StandardOpsDialect,
                  mlir::scf::SCFDialect,
                  mlir::tensor::TensorDialect>();
}

int getConstIndex(tensor::ExtractOp &op) {
  //TODO: check if there's more and throw an error if yes
  auto index = *op.indices().begin();
  if (auto const_op = llvm::dyn_cast<arith::ConstantOp>(index.getDefiningOp())) {
    return const_op.getValue().dyn_cast<IntegerAttr>().getValue().getLimitedValue();
  } else {
    emitError(index.getLoc(), "Index not defined by a constant op!");
    return -1;
  }
}

int getConstIndex(tensor::InsertOp &op) {
  //TODO: check if there's more and throw an error if yes
  auto index = *op.indices().begin();
  if (auto const_op = llvm::dyn_cast<arith::ConstantOp>(index.getDefiningOp())) {
    return const_op.getValue().dyn_cast<IntegerAttr>().getValue().getLimitedValue();
  } else {
    emitError(index.getLoc(), "Index not defined by a constant op!");
    return -1;
  }
}

Value resolveToSlot(int slot, Value v, IRRewriter &rewriter) {
  //TODO: This is the naive/dumb way, no checking if stuff has already happened!
  auto op = v.getDefiningOp();

  if (op) {
    //std::cout << "resolving slot for" << std::endl;
    //op->dump();

    if (auto extract_op = llvm::dyn_cast<tensor::ExtractOp>(op)) {
      // if it's an extract op, simply rotate to bring to right slot
      int extracted_index = getConstIndex(extract_op);
      int offset = extracted_index - slot;
      rewriter.setInsertionPointAfter(extract_op);
      auto new_val = rewriter.create<fhe::RotateOp>(extract_op.getLoc(),
                                                    extract_op.tensor().getType(),
                                                    extract_op.tensor(),
                                                    rewriter.getIndexAttr(offset));

      //extract_op.result().replaceAllUsesWith(new_val);
      //std::cout << "resolved extract to" << std::endl;
      //new_val.dump();
      return new_val;
    } else if (auto fhe_add = llvm::dyn_cast<fhe::AddOp>(op)) {
      llvm::SmallVector<Value, 4> new_summands;
      for (auto operand: fhe_add.x()) {
        auto new_val = resolveToSlot(slot, operand, rewriter);
        new_summands.push_back(new_val);
      }
      // and we also need to update the return type for FHE ops.
      // TODO: would be great if we could do this generically!

      rewriter.setInsertionPointAfter(fhe_add);
      auto new_add = rewriter.create<fhe::AddOp>(fhe_add.getLoc(), new_summands.begin()->getType(), new_summands);
      fhe_add->replaceAllUsesWith(new_add);
      //TODO: THIS REQUIRES VERIFY-EACH-ZERO SO THE TYPE SYSTEM DOESN'T COMPLAIN TOO MUCH!

      //std::cout << "resolved add to" << std::endl;
      auto new_val = *new_add->result_begin();
      //new_val.dump();
      return new_val;
    } else if (auto fhe_mul = llvm::dyn_cast<fhe::MultiplyOp>(op)) {
      llvm::SmallVector<Value, 4> new_summands;
      for (auto operand: fhe_mul.x()) {
        auto new_val = resolveToSlot(slot, operand, rewriter);
        new_summands.push_back(new_val);
      }
      // and we also need to update the return type for FHE ops.
      // TODO: would be great if we could do this generically!

      rewriter.setInsertionPointAfter(fhe_mul);
      auto new_mul = rewriter.create<fhe::MultiplyOp>(fhe_mul.getLoc(), new_summands.begin()->getType(), new_summands);
      fhe_mul->replaceAllUsesWith(new_mul);
      //TODO: THIS REQUIRES VERIFY-EACH-ZERO SO THE TYPE SYSTEM DOESN'T COMPLAIN TOO MUCH!


      //std::cout << "resolved mul to" << std::endl;
      auto new_val = *new_mul->result_begin();
      //new_val.dump();
      return new_val;
    } else if (auto fhe_sub = llvm::dyn_cast<fhe::SubOp>(op)) {
      llvm::SmallVector<Value, 4> new_summands;
      for (auto operand: fhe_sub.x()) {
        auto new_val = resolveToSlot(slot, operand, rewriter);
        new_summands.push_back(new_val);
      }
      // and we also need to update the return type for FHE ops.
      // TODO: would be great if we could do this generically!

      rewriter.setInsertionPointAfter(fhe_sub);
      auto new_sub = rewriter.create<fhe::SubOp>(fhe_sub.getLoc(), new_summands.begin()->getType(), new_summands);
      fhe_sub->replaceAllUsesWith(new_sub);
      //TODO: THIS REQUIRES VERIFY-EACH-ZERO SO THE TYPE SYSTEM DOESN'T COMPLAIN TOO MUCH!

      //std::cout << "resolved sub to" << std::endl;
      auto new_val = *new_sub->result_begin();
      //new_val.dump();
      return new_val;
    } else if (auto fhe_rot = llvm::dyn_cast<fhe::RotateOp>(op)) {
      //already solved
      return v;
    } else if (auto fhe_const = llvm::dyn_cast<fhe::ConstOp>(op)) {
      //TODO: What to do about constants?
      return v;
    } else {
      emitError(op->getLoc(), "UNEXPECTED OPERATION.");
      return v;
    }
  } else {
    //ignore, not defined in this part of code (e.g., might be a function param)
    return v;
  }
}

void BatchingPass::runOnOperation() {
  ConversionTarget target(getContext());
  target.addLegalDialect<AffineDialect, StandardOpsDialect, tensor::TensorDialect, scf::SCFDialect>();
  target.addIllegalOp<AffineForOp>();

  // Get the (default) block in the module's only region:
  auto &block = getOperation()->getRegion(0).getBlocks().front();
  IRRewriter rewriter(&getContext());

  /// Struct for batching info
  struct batching_info {
    int slot;
    std::shared_ptr<Value> value;
  };

  /// Lookup stuff
  std::unordered_map<size_t, batching_info> slot_map;



  //TODO: There's very likely a much better way to do this that's not this kind of manual walk!

  // First, read all the tensor.extract info to find the slot for each SSA value
  for (auto f: llvm::make_early_inc_range(block.getOps<FuncOp>())) {
    for (auto op: llvm::make_early_inc_range(f.body().getOps<tensor::ExtractOp>())) {
      int index_int = getConstIndex(op);
      auto val_ptr = std::make_shared<Value>(op.tensor());
      batching_info bi = {index_int, val_ptr};
      size_t hash = hash_value(op.result());
      slot_map.insert({hash, bi});
    }
  }

  // Now visit each InsertOp and translate it (if necessary)
  for (auto f: llvm::make_early_inc_range(block.getOps<FuncOp>())) {
    for (auto op: llvm::make_early_inc_range(f.body().getOps<tensor::InsertOp>())) {

      int target_index_int = getConstIndex(op);
      auto new_op = resolveToSlot(target_index_int, op.scalar(), rewriter);
      op.result().replaceAllUsesWith(op.scalar());

    }
  }

  // We also need to go and resolve any "return" (TODO: probably other stuff, too!)
  for (auto f: llvm::make_early_inc_range(block.getOps<FuncOp>())) {
    for (auto op: llvm::make_early_inc_range(f.body().getOps<mlir::ReturnOp>())) {

      int target_index_int = 0;
      //todo: in the future, this should be -1 and signal "all slots needed" or something like that
      // TODO: we intentionally don't change the return type, since this should be scalar-ish
      auto new_value = resolveToSlot(target_index_int, op.getOperand(0), rewriter);
      if (new_value!=op.getOperand(0)) {
        op.getOperand(0).replaceAllUsesWith(new_value);
      }
      f.setType(rewriter.getFunctionType(f.getType().getInputs(), new_value.getType()));

      //op.result().replaceAllUsesWith(op.scalar());

    }
  }

}